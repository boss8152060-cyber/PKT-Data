#!/usr/bin/env python3
"""
extract_frames.py —  (Multi Video Tool)

 (  CCTV)  .jpg/.png
 label  /  YOLO 

 CLI ():
    # 
    python extract_frames.py -i video.mp4 -o out_frames

    #  2 
    python extract_frames.py -i video.mp4 -o out_frames --fps 2

    #  30  (  30fps  1 /)
    python extract_frames.py -i video.mp4 -o out_frames --interval 30

    #  00:07:00  00:09:00 
    python extract_frames.py -i video.mp4 -o out_frames --fps 1 --start 00:07:00 --end 00:09:00

    #  () 
    python extract_frames.py -i videos_folder -o out_frames --fps 1 --resize 1280x720

 GUI ():
    python extract_frames.py
    ( argument   GUI )

 dependency  ():
    pip install opencv-python
"""

import argparse
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".m4v", ".ts"}


def _open_video_capture(path):
    """ cv2.VideoCapture  fallback  path / Windows
    ( path  ASCII   Windows short path )"""
    import cv2

    path_str = str(path)
    cap = cv2.VideoCapture(path_str)
    if cap.isOpened():
        return cap

    if sys.platform == "win32":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(260)
            n = ctypes.windll.kernel32.GetShortPathNameW(path_str, buf, 260)
            if n and buf.value and buf.value != path_str:
                cap2 = cv2.VideoCapture(buf.value)
                if cap2.isOpened():
                    return cap2
        except Exception:
            pass

    return cap  # Original (isOpened()  False Actual)


def _open_video_writer(path, fourcc, fps, size):
    """ cv2.VideoWriter  fallback  path / Windows
    ( path  ASCII   imwrite)"""
    import cv2

    path_str = str(path)
    Path(path_str).parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(path_str, fourcc, fps, size)
    if writer.isOpened():
        return writer, path_str

    if sys.platform == "win32":
        try:
            import ctypes

            # short path /  short path 
            #  ( ASCII ) 
            parent = Path(path_str).parent
            buf = ctypes.create_unicode_buffer(260)
            n = ctypes.windll.kernel32.GetShortPathNameW(str(parent), buf, 260)
            if n and buf.value:
                alt_path = str(Path(buf.value) / Path(path_str).name)
                if alt_path != path_str:
                    writer2 = cv2.VideoWriter(alt_path, fourcc, fps, size)
                    if writer2.isOpened():
                        return writer2, alt_path
        except Exception:
            pass

    return writer, path_str  # Original (isOpened()  False Actual)


def _write_image(fpath, frame, img_format, quality):
    """ path / ( cv2.imwrite 
     Windows  path  ASCII )"""
    import cv2

    ext = f".{img_format.lower()}"
    if img_format.lower() in ("jpg", "jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    else:
        params = []
    ok, buf = cv2.imencode(ext, frame, params)
    if not ok:
        return False
    buf.tofile(str(fpath))
    return True


def parse_timestamp(ts):
    """ 'HH:MM:SS' / 'MM:SS' /   (float)"""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    ts = str(ts).strip()
    if ts == "":
        return None
    parts = ts.split(":")
    parts = [float(p) for p in parts]
    if len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = parts
        return m * 60 + s
    elif len(parts) == 1:
        return parts[0]
    raise ValueError(f"Invalid time format: {ts}")


def parse_resize(spec):
    """ 'WIDTHxHEIGHT'  (width, height)"""
    if not spec:
        return None
    spec = spec.lower().replace(" ", "")
    w, h = spec.split("x")
    return (int(w), int(h))


def _find_ffprobe():
    """ ffprobe  ( ffmpeg )  path  None"""
    import shutil as _shutil

    exe_name = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    found = _shutil.which(exe_name) or _shutil.which("ffprobe")
    if found:
        return found
    local = Path(__file__).resolve().parent / "ffmpeg" / exe_name
    if local.exists():
        return str(local)
    return None


def probe_video_info(video_path):
    """ (fps, , )  
     dict {fps, total_frames, duration_sec}  None 

    :  frame count  OpenCV 
    stream copy  ()  ffprobe
    () """
    import cv2

    cap = _open_video_capture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = total_frames / fps if fps else 0

    ffprobe_path = _find_ffprobe()
    if ffprobe_path:
        try:
            import subprocess

            result = subprocess.run(
                [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video_path)],
                capture_output=True, text=True, timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            probed_duration = float(result.stdout.strip())
            if probed_duration > 0 and fps > 0:
                #  OpenCV  ffprobe  (>5%)  ffprobe  ()
                if duration <= 0 or abs(probed_duration - duration) / max(duration, 0.01) > 0.05:
                    duration = probed_duration
                    total_frames = round(duration * fps)
        except Exception:
            pass

    return {"fps": fps, "total_frames": total_frames, "duration_sec": duration}


def format_hms(seconds):
    """ (float)  HH:MM:SS"""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def compute_frame_step(video_fps, fps=None, interval_frames=None):
    """   fps Target interval 
     GUI """
    if fps is not None and fps > 0:
        return max(1, round(video_fps / fps))
    elif interval_frames is not None:
        return max(1, int(interval_frames))
    return 1


def estimate_extraction(video_fps, total_frames, start_sec, end_sec, fps=None, interval_frames=None):
    """  /  ()"""
    start_frame = int(start_sec * video_fps) if start_sec is not None else 0
    end_frame = int(end_sec * video_fps) if end_sec is not None else total_frames
    end_frame = min(end_frame, total_frames)
    span = max(0, end_frame - start_frame)
    if span <= 0:
        return 0
    frame_step = compute_frame_step(video_fps, fps=fps, interval_frames=interval_frames)
    return (span + frame_step - 1) // frame_step  # ceil division —  extract_frames 


def format_size(num_bytes):
    """  '12.3 MB'"""
    if num_bytes is None:
        return "-"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


#  —   ()
#  sensor noise  ( noise )
DEDUP_LEVELS = {"low": 0.5, "medium": 1.5, "high": 3.0}

#  sampling  ( >= N )  seek Target
#  H.264  keyframe  1  2  —  seek Original
# ( seek  )  seek  (1.7x - 3x+)
SEEK_MODE_MIN_STEP = 80

#  ( grab/read   seek-mode)
#   thread 
# ( thread  VideoCapture  — OpenCV/FFmpeg  GIL
#  core)  overhead  VideoCapture
#    SEEK_MODE_MIN_STEP 
#
# :  dedup ()  
#  — 
# ( )
PARALLEL_SINGLE_VIDEO_MIN_FRAMES = 4000


def _make_dedup_thumb(frame):
    """  ( )"""
    import cv2

    small = cv2.resize(frame, (64, 64), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)


def _frame_diff_percent(thumb_a, thumb_b):
    """  (0 = , 100 = )"""
    import cv2

    diff = cv2.absdiff(thumb_a, thumb_b)
    return float(diff.mean()) / 255.0 * 100.0


def _extract_frame_range(
    video_path,
    output_dir,
    video_fps,
    frame_step,
    chunk_start,
    chunk_end,
    img_format,
    quality,
    resize,
    prefix,
    log,
    cancel_event,
    progress_callback,
    dedup_enabled,
    dedup_threshold,
):
    """ [chunk_start, chunk_end)   VideoCapture
      instance  —  ( = 1 
    Original)  thread  (
    _extract_frames_single_parallel )

    chunk_start  ""  (
    (chunk_start - )  frame_step ) 
    

     tuple: (saved_count, cancelled, skipped_dedup, diff_stats)
    """
    import cv2

    cap = _open_video_capture(video_path)
    if not cap.isOpened():
        log(f"[ERROR]  ( {chunk_start}-{chunk_end}): {video_path}")
        return 0, False, 0, []

    saved_count = 0
    cancelled = False
    last_saved_thumb = None
    skipped_dedup = 0
    diff_stats = []
    frames_to_process = max(1, chunk_end - chunk_start)

    def try_save_frame(frame, at_frame_idx):
        nonlocal saved_count, last_saved_thumb, skipped_dedup
        should_save = True
        if dedup_enabled:
            thumb = _make_dedup_thumb(frame)
            if last_saved_thumb is not None:
                diff_pct = _frame_diff_percent(thumb, last_saved_thumb)
                diff_stats.append(diff_pct)
                if diff_pct < dedup_threshold:
                    should_save = False
                    skipped_dedup += 1
            if should_save:
                last_saved_thumb = thumb

        if should_save:
            f = frame
            if resize:
                f = cv2.resize(f, resize, interpolation=cv2.INTER_AREA)
            timestamp_sec = at_frame_idx / video_fps
            fname = f"{prefix}_frame{at_frame_idx:06d}_t{timestamp_sec:.2f}s.{img_format}"
            fpath = Path(output_dir) / fname
            if _write_image(fpath, f, img_format, quality):
                saved_count += 1
            else:
                log(f"[WARN] : {fname}")

    use_seek_mode = frame_step >= SEEK_MODE_MIN_STEP
    frame_idx = chunk_start
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

    if use_seek_mode:
        total_targets = max(1, (frames_to_process + frame_step - 1) // frame_step)
        target_count = 0
        while frame_idx < chunk_end:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
            try_save_frame(frame, frame_idx)
            target_count += 1
            frame_idx += frame_step
            if progress_callback is not None:
                progress_callback(min(target_count * frame_step, frames_to_process), frames_to_process)
    else:
        while frame_idx < chunk_end:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break

            is_target = (frame_idx - chunk_start) % frame_step == 0
            if is_target:
                ret, frame = cap.read()
                if not ret:
                    break
                try_save_frame(frame, frame_idx)
            else:
                ret = cap.grab()
                if not ret:
                    break
            frame_idx += 1

            processed = frame_idx - chunk_start
            if progress_callback is not None and (processed % 10 == 0 or processed >= frames_to_process):
                progress_callback(min(processed, frames_to_process), frames_to_process)

    cap.release()
    if progress_callback is not None and not cancelled:
        progress_callback(frames_to_process, frames_to_process)
    return saved_count, cancelled, skipped_dedup, diff_stats


def _extract_frames_single_parallel(
    video_path,
    output_dir,
    video_fps,
    frame_step,
    start_frame,
    end_frame,
    img_format,
    quality,
    resize,
    prefix,
    log,
    cancel_event,
    progress_callback,
    dedup_enabled,
    dedup_threshold,
    max_workers,
):
    """ (chunk)  thread 
    VideoCapture   — / (
    PARALLEL_SINGLE_VIDEO_MIN_FRAMES)  seek ()
     tuple: (saved_count, cancelled, skipped_dedup, diff_stats) 
    """
    import threading as _threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total_targets = max(1, (end_frame - start_frame + frame_step - 1) // frame_step)
    max_workers = max(1, min(max_workers, total_targets))
    chunk_target_size = max(1, (total_targets + max_workers - 1) // max_workers)

    #  "Target"   
    #  
    chunks = []
    cursor = start_frame
    chunk_idx = 0
    while cursor < end_frame:
        end_target_idx = min(total_targets, (chunk_idx + 1) * chunk_target_size)
        chunk_end = min(end_frame, start_frame + end_target_idx * frame_step)
        if chunk_end <= cursor:
            break
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
        chunk_idx += 1

    log(f"[INFO]  {len(chunks)}  (/)")
    if dedup_enabled:
        log("[]  dedup  —  ")
        log("            ()")

    total_frames_all = max(1, end_frame - start_frame)
    progress_lock = _threading.Lock()
    progress_map = {i: 0 for i in range(len(chunks))}
    saved_total = 0
    any_cancelled = False
    skipped_dedup_total = 0
    diff_stats_all = []

    def make_cb(idx):
        def cb(done, _total_this_chunk):
            with progress_lock:
                progress_map[idx] = done
                current = sum(progress_map.values())
            if progress_callback is not None:
                progress_callback(min(current, total_frames_all), total_frames_all)

        return cb

    def worker(idx, c_start, c_end):
        return _extract_frame_range(
            video_path, output_dir, video_fps, frame_step, c_start, c_end,
            img_format, quality, resize, prefix, log, cancel_event,
            make_cb(idx), dedup_enabled, dedup_threshold,
        )

    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {executor.submit(worker, i, c[0], c[1]): i for i, c in enumerate(chunks)}
        for future in as_completed(futures):
            try:
                n, cancelled, skipped, diffs = future.result()
                saved_total += n
                any_cancelled = any_cancelled or cancelled
                skipped_dedup_total += skipped
                diff_stats_all.extend(diffs)
            except Exception as e:
                log(f"[ERROR] {e}")

    return saved_total, any_cancelled, skipped_dedup_total, diff_stats_all


def extract_frames(
    video_path,
    output_dir,
    fps=None,
    interval_frames=None,
    start_sec=None,
    end_sec=None,
    img_format="jpg",
    quality=95,
    resize=None,
    prefix=None,
    log=print,
    cancel_event=None,
    progress_callback=None,
    dedup_enabled=False,
    dedup_threshold=3.0,
    max_workers=None,
):
    """ 

    cancel_event: threading.Event  set() 
    progress_callback:  callback(frames_done, frames_total) 
    dedup_enabled:  True  ()
    dedup_threshold:  (% )  — 
    max_workers:  thread  (
        PARALLEL_SINGLE_VIDEO_MIN_FRAMES)  os.cpu_count() 
         1 Original ()
    """
    import os as _os

    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    info = probe_video_info(video_path)
    if info is None:
        log(f"[ERROR] : {video_path}")
        return 0

    video_fps = info["fps"]
    total_frames = info["total_frames"]
    duration = info["duration_sec"]

    frame_step = compute_frame_step(video_fps, fps=fps, interval_frames=interval_frames)
    start_frame = int(start_sec * video_fps) if start_sec is not None else 0
    end_frame = int(end_sec * video_fps) if end_sec is not None else total_frames
    end_frame = min(end_frame, total_frames)
    prefix = prefix or video_path.stem

    log(f"[INFO] {video_path.name}: {video_fps:.2f} FPS, {total_frames} , {duration:.1f} ")
    log(f"[INFO]  {frame_step}  ( {start_frame}-{end_frame})")

    frames_to_process = max(1, end_frame - start_frame)
    use_seek_mode = frame_step >= SEEK_MODE_MIN_STEP

    if max_workers is None:
        max_workers = max(1, _os.cpu_count() or 2)

    #  ( thread )  :
    #  seek-mode  (), /,
    #  1 core 
    should_parallelize = (
        not use_seek_mode and frames_to_process >= PARALLEL_SINGLE_VIDEO_MIN_FRAMES and max_workers > 1
    )

    if should_parallelize:
        saved_count, cancelled, skipped_dedup, diff_stats = _extract_frames_single_parallel(
            video_path, output_dir, video_fps, frame_step, start_frame, end_frame,
            img_format, quality, resize, prefix, log, cancel_event,
            progress_callback, dedup_enabled, dedup_threshold, max_workers,
        )
    else:
        saved_count, cancelled, skipped_dedup, diff_stats = _extract_frame_range(
            video_path, output_dir, video_fps, frame_step, start_frame, end_frame,
            img_format, quality, resize, prefix, log, cancel_event,
            progress_callback, dedup_enabled, dedup_threshold,
        )

    if cancelled:
        log(f"[]  —  {saved_count}  -> {output_dir}")
    else:
        if dedup_enabled:
            if diff_stats:
                log(
                    f"[INFO] dedup:  {skipped_dedup}/{len(diff_stats)}  "
                    f"(  {min(diff_stats):.2f}%  {max(diff_stats):.2f}% "
                    f" {sum(diff_stats)/len(diff_stats):.2f}% |  {dedup_threshold:.1f}%)"
                )
                if skipped_dedup == 0 and min(diff_stats) > dedup_threshold:
                    log(
                        f"[]   ({min(diff_stats):.2f}%) "
                        f" ({dedup_threshold:.1f}%) —  noise/ "
                        f"  \"\" "
                    )
            else:
                log("[INFO] dedup:  2  ")
        if progress_callback is not None:
            progress_callback(frames_to_process, frames_to_process)
        log(f"[DONE]  {saved_count}  -> {output_dir}")
    return saved_count


def _process_videos_parallel(
    videos, output_dir, log, cancel_event, video_progress_callback, progress_callback, max_workers, **kwargs
):
    """ thread pool (OpenCV  GIL /
     thread  process) """
    import os
    import threading as _threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if max_workers is None:
        max_workers = min(4, max(1, os.cpu_count() or 2))

    log(f"[INFO]  {max_workers}  ( {len(videos)} )")
    if video_progress_callback is not None:
        video_progress_callback(0, len(videos), f" {len(videos)} ...")

    #   % 
    frame_counts = {}
    total_frames_all = 0
    for v in videos:
        info = probe_video_info(v)
        cnt = info["total_frames"] if info else 0
        frame_counts[v] = cnt
        total_frames_all += cnt

    progress_lock = _threading.Lock()
    progress_map = {v: 0 for v in videos}
    state = {"completed": 0, "saved_total": 0}

    def make_progress_cb(v):
        def cb(done, _total_this_video):
            with progress_lock:
                progress_map[v] = done
                current = sum(progress_map.values())
                completed = state["completed"]
            if progress_callback is not None and total_frames_all > 0:
                progress_callback(current, total_frames_all)
            if video_progress_callback is not None:
                video_progress_callback(completed, len(videos), f" {len(videos)} ...")

        return cb

    def worker(v):
        sub_out = Path(output_dir) / v.stem
        prefixed_log = lambda msg, _name=v.name: log(f"[{_name}] {msg}")
        n = extract_frames(
            v, sub_out, log=prefixed_log, cancel_event=cancel_event,
            progress_callback=make_progress_cb(v), **kwargs
        )
        with progress_lock:
            state["saved_total"] += n
            state["completed"] += 1
        return n

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, v): v for v in videos}
        for future in as_completed(futures):
            v = futures[future]
            try:
                future.result()
            except Exception as e:
                log(f"[ERROR] {v.name}: {e}")

    return state["saved_total"]


def process_input(
    input_path, output_dir, log=print, cancel_event=None,
    video_progress_callback=None, progress_callback=None,
    parallel=True, max_workers=None, **kwargs
):
    """

    video_progress_callback:  callback(index, total_videos, video_name) 
    parallel:  True  1   ()
    """
    input_path = Path(input_path)
    total = 0

    if input_path.is_dir():
        videos = sorted(p for p in input_path.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
        if not videos:
            log(f"[WARN] : {input_path}")
            return 0

        if parallel and len(videos) > 1:
            total = _process_videos_parallel(
                videos, output_dir, log=log, cancel_event=cancel_event,
                video_progress_callback=video_progress_callback, progress_callback=progress_callback,
                max_workers=max_workers, **kwargs
            )
        else:
            for i, v in enumerate(videos, start=1):
                if cancel_event is not None and cancel_event.is_set():
                    log("[] ")
                    break
                if video_progress_callback is not None:
                    video_progress_callback(i, len(videos), v.name)
                sub_out = Path(output_dir) / v.stem
                total += extract_frames(
                    v, sub_out, log=log, cancel_event=cancel_event,
                    progress_callback=progress_callback, **kwargs
                )
        log(f"\n[SUMMARY]  {total}   {len(videos)} ")
    elif input_path.is_file():
        if video_progress_callback is not None:
            video_progress_callback(1, 1, input_path.name)
        total = extract_frames(
            input_path, output_dir, log=log, cancel_event=cancel_event,
            progress_callback=progress_callback, **kwargs
        )
    else:
        log(f"[ERROR] : {input_path}")

    return total


def _find_ffmpeg():
    """ ffmpeg   path  ffmpeg  None 
     PATH   ffmpeg/  """
    import shutil as _shutil

    exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    found = _shutil.which(exe_name) or _shutil.which("ffmpeg")
    if found:
        return found
    local = Path(__file__).resolve().parent / "ffmpeg" / exe_name
    if local.exists():
        return str(local)
    return None


def _run_ffmpeg(cmd, log, timeout=1800):
    """ ffmpeg  console   True  (returncode 0)"""
    import subprocess

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        log(f"[]  ffmpeg : {e}")
        return False

    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-1:] or [""]
        log(f"[] ffmpeg  error: {tail[0][:200]}")
        return False
    return True


def _ffmpeg_trim(ffmpeg_path, video_path, output_path, start_sec, end_sec, log):
    """ ffmpeg  stream copy (   keyframe
     )  True/False """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg_path, "-y"]
    if start_sec is not None:
        cmd += ["-ss", f"{start_sec:.3f}"]
    cmd += ["-i", str(video_path)]
    if start_sec is not None and end_sec is not None:
        cmd += ["-t", f"{max(0.0, end_sec - start_sec):.3f}"]
    elif end_sec is not None:
        cmd += ["-t", f"{end_sec:.3f}"]
    cmd += ["-c", "copy", str(output_path)]

    log("[INFO]  ffmpeg ( )...")
    if not _run_ffmpeg(cmd, log):
        return False
    if not output_path.exists() or output_path.stat().st_size == 0:
        log("[] ffmpeg ")
        return False

    log(f"[DONE]  ffmpeg -> {output_path}")
    return True


def trim_video(
    video_path,
    output_path,
    start_sec=None,
    end_sec=None,
    log=print,
    cancel_event=None,
    progress_callback=None,
    fast_mode=True,
):
    """   True/False 

    fast_mode:  True  ffmpeg  stream copy ( 
    keyframe   ≤ ~2 )  False  ffmpeg 
     OpenCV  ( )
    """
    video_path = Path(video_path)

    if fast_mode:
        ffmpeg_path = _find_ffmpeg()
        if ffmpeg_path:
            if _ffmpeg_trim(ffmpeg_path, video_path, output_path, start_sec, end_sec, log):
                if progress_callback is not None:
                    progress_callback(1, 1)
                return True
            log("[INFO]  ()")
        else:
            log("[]  ffmpeg   ()")

    return _trim_video_opencv(video_path, output_path, start_sec, end_sec, log, cancel_event, progress_callback)


def _trim_video_opencv(video_path, output_path, start_sec, end_sec, log, cancel_event, progress_callback):
    """ OpenCV (,  ffmpeg
    )  True/False """
    import cv2

    video_path = Path(video_path)
    cap = _open_video_capture(video_path)
    if not cap.isOpened():
        log(f"[ERROR] : {video_path}")
        return False

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start_frame = int(start_sec * fps) if start_sec is not None else 0
    end_frame = int(end_sec * fps) if end_sec is not None else total_frames
    end_frame = min(end_frame, total_frames)
    span = max(0, end_frame - start_frame)

    if span <= 0:
        log("[ERROR]  ( >=  )")
        cap.release()
        return False

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer, actual_path = _open_video_writer(output_path, fourcc, fps, (width, height))
    if not writer.isOpened():
        log(f"[ERROR] : {output_path}")
        cap.release()
        return False

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_idx = start_frame
    written = 0
    cancelled = False
    log(f"[INFO]  {video_path.name}: {format_hms(start_frame / fps)} - {format_hms(end_frame / fps)} ({span} )")

    while frame_idx < end_frame:
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            log(f"[]  —  {written} ")
            break
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)
        written += 1
        frame_idx += 1
        if progress_callback is not None and span > 0 and (written % max(1, span // 200) == 0 or written == span):
            progress_callback(written, span)

    cap.release()
    writer.release()

    if cancelled:
        return False

    if written <= 0:
        log("[ERROR]  ")
        return False

    log(f"[DONE]  {written}  -> {actual_path}")
    return True


def _probe_video_params(video_path):
    """ (/fps/fourcc)  ffmpeg stream copy 
    (  stream copy )"""
    import cv2

    cap = _open_video_capture(video_path)
    if not cap.isOpened():
        return None
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = round(cap.get(cv2.CAP_PROP_FPS) or 0, 2)
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    cap.release()
    return (w, h, fps, fourcc)


def _ffmpeg_concat(ffmpeg_path, video_paths, output_path, log):
    """ ffmpeg concat demuxer  stream copy ( )
    /fps/codec   True/False"""
    import tempfile

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def esc(p):
        return str(Path(p).resolve()).replace("'", "'\\''")

    list_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            for p in video_paths:
                f.write(f"file '{esc(p)}'\n")
            list_path = f.name

        cmd = [ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", str(output_path)]
        log("[INFO]  ffmpeg ( )...")
        if not _run_ffmpeg(cmd, log):
            return False
    finally:
        if list_path:
            try:
                Path(list_path).unlink()
            except Exception:
                pass

    if not output_path.exists() or output_path.stat().st_size == 0:
        log("[] ffmpeg ")
        return False

    log(f"[DONE]  ffmpeg -> {output_path}")
    return True


def merge_videos(
    video_paths,
    output_path,
    log=print,
    cancel_event=None,
    progress_callback=None,
    fast_mode=True,
):
    """   True/False

    fast_mode:  True,  ffmpeg, /fps/codec  
    stream copy ( )  ffmpeg 
     OpenCV  ( )
    """
    video_paths = [Path(p) for p in video_paths]
    if len(video_paths) < 2:
        log("[ERROR]  2 ")
        return False

    if fast_mode:
        ffmpeg_path = _find_ffmpeg()
        if ffmpeg_path:
            params_list = [_probe_video_params(p) for p in video_paths]
            if all(p is not None for p in params_list) and len(set(params_list)) == 1:
                if _ffmpeg_concat(ffmpeg_path, video_paths, output_path, log):
                    if progress_callback is not None:
                        progress_callback(1, 1)
                    return True
                log("[INFO]  ()")
            else:
                log(
                    "[] /fps/ "
                    " ( ffmpeg )"
                )
        else:
            log("[]  ffmpeg  ")

    return _merge_videos_opencv(video_paths, output_path, log, cancel_event, progress_callback)


def _merge_videos_opencv(video_paths, output_path, log, cancel_event, progress_callback):
    """ OpenCV  fps/
    /  True/False """
    import cv2

    #  fps/
    first_info = probe_video_info(video_paths[0])
    if first_info is None:
        log(f"[ERROR] : {video_paths[0]}")
        return False

    cap0 = _open_video_capture(video_paths[0])
    width = int(cap0.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap0.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap0.release()
    fps = first_info["fps"]
    target_size = (width, height)

    #   % 
    infos = [first_info]
    for p in video_paths[1:]:
        info = probe_video_info(p)
        if info is None:
            log(f"[ERROR] : {p}")
            return False
        infos.append(info)
    total_frames_all = sum(i["total_frames"] for i in infos)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer, actual_path = _open_video_writer(output_path, fourcc, fps, target_size)
    if not writer.isOpened():
        log(f"[ERROR] : {output_path}")
        return False

    written_total = 0
    cancelled = False
    for idx, (path, info) in enumerate(zip(video_paths, infos), start=1):
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            break
        log(f"[INFO] ({idx}/{len(video_paths)}) : {path.name}")
        cap = _open_video_capture(path)
        if not cap.isOpened():
            log(f"[WARN] : {path.name}")
            continue

        this_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        this_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        needs_resize = (this_w, this_h) != target_size
        if needs_resize:
            log(f"[] {path.name}  {this_w}x{this_h}  ({width}x{height}) — ")

        while True:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break
            ret, frame = cap.read()
            if not ret:
                break
            if needs_resize:
                frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)
            writer.write(frame)
            written_total += 1
            if progress_callback is not None and total_frames_all > 0:
                step = max(1, total_frames_all // 200)
                if written_total % step == 0 or written_total == total_frames_all:
                    progress_callback(written_total, total_frames_all)
        cap.release()
        if cancelled:
            break

    writer.release()

    if cancelled:
        log(f"[]  —  {written_total} ")
        return False

    if written_total <= 0:
        log("[ERROR]  ")
        return False

    log(f"[DONE]  {len(video_paths)}   {written_total}  -> {actual_path}")
    return True


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def _read_image_safe(path):
    """ path / ( cv2.imread  
    path  ASCII  Windows )  numpy array  None"""
    import cv2
    import numpy as np

    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def images_to_video(image_paths, output_path, fps=25.0, log=print, cancel_event=None, progress_callback=None):
    """ 
     /  True/False"""
    import cv2

    image_paths = [Path(p) for p in image_paths]
    if len(image_paths) < 1:
        log("[ERROR]  1 ")
        return False
    if fps is None or fps <= 0:
        log("[ERROR] FPS  0")
        return False

    first_img = _read_image_safe(image_paths[0])
    if first_img is None:
        log(f"[ERROR] : {image_paths[0]}")
        return False

    h, w = first_img.shape[:2]
    target_size = (w, h)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer, actual_path = _open_video_writer(output_path, fourcc, fps, target_size)
    if not writer.isOpened():
        log(f"[ERROR] : {output_path}")
        return False

    total = len(image_paths)
    written = 0
    cancelled = False
    log(f"[INFO]  {total}   {fps} FPS ( {w}x{h})...")

    for idx, img_path in enumerate(image_paths):
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            log(f"[]  —  {written} ")
            break

        img = _read_image_safe(img_path)
        if img is None:
            log(f"[WARN] : {img_path.name}")
            continue
        if img.shape[1] != w or img.shape[0] != h:
            img = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)
        writer.write(img)
        written += 1

        if progress_callback is not None:
            step = max(1, total // 200)
            if written % step == 0 or written == total:
                progress_callback(written, total)

    writer.release()

    if cancelled:
        return False

    if written <= 0:
        log("[ERROR]  ")
        return False

    log(f"[DONE]  {written}  (~{written / fps:.1f} ) -> {actual_path}")
    return True


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(
        description="",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-i", "--input", help="  ")
    p.add_argument("-o", "--output", default="output_frames", help=" (: output_frames)")
    rate = p.add_mutually_exclusive_group()
    rate.add_argument("--fps", type=float, help="  1, 2, 0.5")
    rate.add_argument("--interval", type=int, help=" N  ( --fps)")
    p.add_argument("--start", help="  HH:MM:SS ")
    p.add_argument("--end", help="  HH:MM:SS ")
    p.add_argument("--format", default="jpg", choices=["jpg", "jpeg", "png"], help=" (: jpg)")
    p.add_argument("--quality", type=int, default=95, help=" JPEG 1-100 (: 95)")
    p.add_argument("--resize", help="  1280x720")
    p.add_argument("--prefix", help=" (: )")
    p.add_argument(
        "--no-parallel", action="store_true",
        help=" ()",
    )
    p.add_argument("--dedup", action="store_true", help="/")
    p.add_argument(
        "--dedup-level", default="medium", choices=["low", "medium", "high"],
        help=" --dedup (: medium)",
    )
    p.add_argument("--gui", action="store_true", help=" (GUI)")
    return p


def run_cli(args):
    if not args.input:
        print("[ERROR] Input is required: -i/--input (video file or folder)")
        sys.exit(1)

    try:
        start_sec = parse_timestamp(args.start)
        end_sec = parse_timestamp(args.end)
        resize = parse_resize(args.resize)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    last_printed = {"pct": -10}

    def cli_progress(done, total):
        pct = int(done / total * 100) if total else 0
        if pct - last_printed["pct"] >= 10 or pct >= 100:
            print(f"[Progress] {pct}%")
            last_printed["pct"] = pct

    process_input(
        args.input,
        args.output,
        fps=args.fps,
        interval_frames=args.interval,
        start_sec=start_sec,
        end_sec=end_sec,
        img_format=args.format,
        quality=args.quality,
        resize=resize,
        prefix=args.prefix,
        progress_callback=cli_progress,
        parallel=not args.no_parallel,
        dedup_enabled=args.dedup,
        dedup_threshold=DEDUP_LEVELS.get(args.dedup_level, 1.5),
    )


# --------------------------------------------------------------------------
# GUI (tkinter —  Python  )
# --------------------------------------------------------------------------

def launch_gui(parent=None, visible_tools=None):
    """ Multi Video Tool —  parent   (
    Original)  parent  (  PK Studio) 
    ttk.Frame  parent   return  Frame  pack()
     —  (2500+ )  root 
    .pack()/.after()  tk.Tk()  ttk.Frame 
    

    visible_tools  PK Studio:
    extract, trim, merge, images_to_video. Original
    """
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk, simpledialog

    standalone = parent is None
    if standalone:
        root = tk.Tk()
        root.title("Multi Video Tool")
        root.geometry("780x760")
        root.minsize(680, 420)
        root.resizable(True, True)
    else:
        root = ttk.Frame(parent)

    pad = {"padx": 10, "pady": 4}

    def make_scrollable_tab(parent):
        """ (scrollable) +   
         (content_frame, button_holder_frame) —  content_frame  button_holder_frame"""
        button_holder = ttk.Frame(parent)
        button_holder.pack(side="bottom", fill="x", pady=8)

        canvas_frame = tk.Frame(parent)
        canvas_frame.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        content_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _resize(event):
            canvas.itemconfig(content_window, width=event.width)

        canvas.bind("<Configure>", _resize)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_wheel(event):
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # bind  canvas  ()
        canvas.bind("<Enter>", lambda e: (canvas.bind_all("<MouseWheel>", _on_wheel), canvas.bind_all("<Button-4>", _on_wheel), canvas.bind_all("<Button-5>", _on_wheel)))
        canvas.bind("<Leave>", lambda e: (canvas.unbind_all("<MouseWheel>"), canvas.unbind_all("<Button-4>"), canvas.unbind_all("<Button-5>")))

        return content_frame, button_holder

    # ---  ---
    if visible_tools is None:
        visible_tools = {"extract", "trim", "merge", "images_to_video"}
    else:
        visible_tools = set(visible_tools)

    #  PK Studio   Notebook 
    visible_count = len(visible_tools)
    notebook = None
    if visible_count > 1:
        notebook = ttk.Notebook(root)
        notebook.pack(side="top", fill="both", expand=True)

    def _make_tool_tab(text):
        parent_frame = notebook if notebook is not None else root
        frame = ttk.Frame(parent_frame)
        if notebook is not None:
            notebook.add(frame, text=text)
        else:
            frame.pack(fill="both", expand=True)
        return frame

    tab_extract = _make_tool_tab("1. Extract Frames") if "extract" in visible_tools else ttk.Frame(root)

    content, run_btn_holder = make_scrollable_tab(tab_extract)

    extract_queue = []  # queued videos; each item stores path and metadata
    output_var = tk.StringVar(value=str(Path.cwd() / "output_frames"))
    mode_var = tk.StringVar(value="fps")
    rate_var = tk.StringVar(value="1")
    format_var = tk.StringVar(value="jpg")
    resize_var = tk.StringVar()
    prefix_var = tk.StringVar()
    dedup_var = tk.BooleanVar(value=False)
    dedup_level_var = tk.StringVar(value="medium")
    estimate_total_var = tk.StringVar(value="-")

    # --- 1)  ---
    frm_in = ttk.LabelFrame(content, text="1) Video Queue")
    frm_in.pack(fill="x", **pad)

    queue_listbox_frame = ttk.Frame(frm_in)
    queue_listbox_frame.pack(fill="x", padx=6, pady=6)
    queue_listbox = tk.Listbox(queue_listbox_frame, height=6, selectmode="extended")
    queue_listbox.pack(side="left", fill="both", expand=True)
    queue_scrollbar = ttk.Scrollbar(queue_listbox_frame, orient="vertical", command=queue_listbox.yview)
    queue_scrollbar.pack(side="left", fill="y")
    queue_listbox.configure(yscrollcommand=queue_scrollbar.set)

    def queue_refresh_listbox():
        queue_listbox.delete(0, "end")
        for i, item in enumerate(extract_queue, start=1):
            info = item.get("info")
            dur_txt = format_hms(info["duration_sec"]) if info else "Reading..."
            trim_txt = ""
            if item.get("start") or item.get("end"):
                trim_txt = ""
            queue_listbox.insert("end", f"{i}. {Path(item['path']).name}  ({dur_txt}){trim_txt}")
        queue_count_var.set(f"{len(extract_queue)} videos")
        schedule_estimate_update()

    def probe_queue_items(items):
        """Read video metadata in the background without decoding preview frames."""
        def worker():
            for item in items:
                if item.get("info") is None:
                    item["info"] = probe_video_info(item["path"])
            root.after(0, queue_refresh_listbox)

        threading.Thread(target=worker, daemon=True).start()

    def queue_add_files():
        paths = filedialog.askopenfilenames(
            title="Select video files",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.ts"), ("All files", "*.*")],
        )
        if not paths:
            return
        new_items = [{"path": p, "info": None} for p in paths]
        extract_queue.extend(new_items)
        queue_refresh_listbox()
        probe_queue_items(new_items)

    def queue_add_folder():
        folder = filedialog.askdirectory(title="Select a folder containing videos")
        if not folder:
            return
        found = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
        if not found:
            messagebox.showinfo("No videos found", "No video files found in the selected folder.")
            return
        new_items = [{"path": str(p), "info": None} for p in found]
        extract_queue.extend(new_items)
        queue_refresh_listbox()
        probe_queue_items(new_items)

    def queue_remove_selected():
        sel = list(queue_listbox.curselection())
        for idx in reversed(sel):
            del extract_queue[idx]
        queue_refresh_listbox()

    def queue_move_up():
        sel = list(queue_listbox.curselection())
        if not sel or sel[0] == 0:
            return
        for idx in sel:
            extract_queue[idx - 1], extract_queue[idx] = extract_queue[idx], extract_queue[idx - 1]
        queue_refresh_listbox()
        for idx in sel:
            queue_listbox.selection_set(idx - 1)

    def queue_move_down():
        sel = list(queue_listbox.curselection())
        if not sel or sel[-1] == len(extract_queue) - 1:
            return
        for idx in reversed(sel):
            extract_queue[idx + 1], extract_queue[idx] = extract_queue[idx], extract_queue[idx + 1]
        queue_refresh_listbox()
        for idx in sel:
            queue_listbox.selection_set(idx + 1)

    def queue_clear_all():
        extract_queue.clear()
        queue_refresh_listbox()

    queue_btn_row = ttk.Frame(frm_in)
    queue_btn_row.pack(fill="x", padx=6, pady=(0, 6))
    ttk.Button(queue_btn_row, text="+ Add Videos...", command=queue_add_files).pack(side="left", padx=(0, 4))
    ttk.Button(queue_btn_row, text="+ Add Folder...", command=queue_add_folder).pack(side="left", padx=4)
    ttk.Button(queue_btn_row, text="- Remove Selected", command=queue_remove_selected).pack(side="left", padx=4)
    ttk.Button(queue_btn_row, text="▲ Move Up", command=queue_move_up).pack(side="left", padx=4)
    ttk.Button(queue_btn_row, text="▼ Move Down", command=queue_move_down).pack(side="left", padx=4)
    ttk.Button(queue_btn_row, text="Clear All", command=queue_clear_all).pack(side="left", padx=4)

    queue_count_var = tk.StringVar(value="0 videos")
    ttk.Label(frm_in, textvariable=queue_count_var).pack(anchor="w", padx=6, pady=(0, 6))

    # --- Output folder ---
    frm_out = ttk.LabelFrame(content, text="2) Output Folder")
    frm_out.pack(fill="x", **pad)
    ttk.Entry(frm_out, textvariable=output_var, width=45).pack(side="left", fill="x", expand=True, padx=6, pady=6)

    def pick_output():
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            output_var.set(path)

    def create_named_folder():
        name = simpledialog.askstring(
            "Create New Folder",
            "Enter a folder name:",
            parent=root,
        )
        if not name or not name.strip():
            return
        new_path = Path(output_var.get()) / name.strip()
        try:
            new_path.mkdir(parents=True, exist_ok=True)
            output_var.set(str(new_path))
        except Exception as e:
            messagebox.showerror("Error", f"Could not create folder: {e}")

    ttk.Button(frm_out, text="Browse...", command=pick_output).pack(side="left", padx=2)
    ttk.Button(frm_out, text="+ New Folder...", command=create_named_folder).pack(side="left", padx=2)

    # ---  ---
    frm_rate = ttk.LabelFrame(content, text="3) Frame Sampling")
    frm_rate.pack(fill="x", **pad)
    ttk.Radiobutton(frm_rate, text="Frames per second (FPS)", variable=mode_var, value="fps").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    ttk.Radiobutton(frm_rate, text="Every N frames", variable=mode_var, value="interval").grid(row=1, column=0, sticky="w", padx=6, pady=4)
    ttk.Entry(frm_rate, textvariable=rate_var, width=10).grid(row=0, column=1, rowspan=2, padx=6)
    ttk.Label(frm_rate, text="(Blank or 0 = every frame)").grid(row=0, column=2, rowspan=2, sticky="w")

    # ---  ---
    frm_misc = ttk.LabelFrame(content, text="4) Output Options")
    frm_misc.pack(fill="x", **pad)
    ttk.Label(frm_misc, text="Image format:").grid(row=0, column=0, padx=6, pady=4, sticky="w")
    ttk.Combobox(frm_misc, textvariable=format_var, values=["jpg", "png"], width=8, state="readonly").grid(row=0, column=1)
    ttk.Label(frm_misc, text="Resize (WxH):").grid(row=0, column=2, padx=6, sticky="w")
    ttk.Entry(frm_misc, textvariable=resize_var, width=12).grid(row=0, column=3)
    ttk.Label(frm_misc, text="Filename prefix:").grid(row=1, column=0, padx=6, pady=4, sticky="w")
    ttk.Entry(frm_misc, textvariable=prefix_var, width=20).grid(row=1, column=1, columnspan=2, sticky="w")

    dedup_level_frame = ttk.Frame(frm_misc)

    def _toggle_dedup_level_frame():
        if dedup_var.get():
            dedup_level_frame.grid(row=3, column=0, columnspan=3, padx=(24, 6), pady=(0, 6), sticky="w")
        else:
            dedup_level_frame.grid_forget()
        schedule_estimate_update()

    ttk.Checkbutton(
        frm_misc, text="Skip near-duplicate frames",
        variable=dedup_var, command=_toggle_dedup_level_frame,
    ).grid(row=2, column=0, columnspan=3, padx=6, pady=(4, 4), sticky="w")

    dedup_custom_var = tk.StringVar(value="1.5")

    def get_dedup_threshold():
        if dedup_level_var.get() == "custom":
            try:
                return float(dedup_custom_var.get())
            except ValueError:
                return DEDUP_LEVELS["medium"]
        return DEDUP_LEVELS.get(dedup_level_var.get(), DEDUP_LEVELS["medium"])

    ttk.Label(dedup_level_frame, text="Deduplication level:").pack(side="left", padx=(0, 6))
    ttk.Radiobutton(
        dedup_level_frame, text="Low (keep more)", variable=dedup_level_var, value="low",
        command=lambda: schedule_estimate_update(),
    ).pack(side="left", padx=4)
    ttk.Radiobutton(
        dedup_level_frame, text="Medium", variable=dedup_level_var, value="medium",
        command=lambda: schedule_estimate_update(),
    ).pack(side="left", padx=4)
    ttk.Radiobutton(
        dedup_level_frame, text="High (keep fewer)", variable=dedup_level_var, value="high",
        command=lambda: schedule_estimate_update(),
    ).pack(side="left", padx=4)
    ttk.Radiobutton(
        dedup_level_frame, text="Custom (%):", variable=dedup_level_var, value="custom",
        command=lambda: schedule_estimate_update(),
    ).pack(side="left", padx=(4, 2))
    ttk.Entry(dedup_level_frame, textvariable=dedup_custom_var, width=6).pack(side="left")

    # ---  ---
    frm_estimate = ttk.LabelFrame(content, text="5) Estimate")
    frm_estimate.pack(fill="x", **pad)
    estimate_label = ttk.Label(frm_estimate, textvariable=estimate_total_var, font=("Segoe UI", 12, "bold"), wraplength=700)
    estimate_label.pack(anchor="w", padx=10, pady=(10, 4))
    estimate_detail_box = tk.Text(frm_estimate, height=5, wrap="word", state="disabled")
    estimate_detail_box.pack(fill="x", padx=10, pady=(0, 10))

    def update_preview_and_estimate():
        """+ """
        if not extract_queue:
            estimate_total_var.set("-")
            estimate_detail_box.configure(state="normal")
            estimate_detail_box.delete("1.0", "end")
            estimate_detail_box.configure(state="disabled")
            return

        try:
            rate = float(rate_var.get()) if rate_var.get().strip() else None
        except ValueError:
            estimate_total_var.set("(Invalid frame rate)")
            estimate_label.configure(foreground="red")
            return
        fps_val = rate if mode_var.get() == "fps" and rate else None
        interval_val = int(rate) if mode_var.get() == "interval" and rate else None

        try:
            resize = parse_resize(resize_var.get()) if resize_var.get().strip() else None
        except ValueError:
            estimate_total_var.set("(Invalid resize format, e.g. 1280x720)")
            estimate_label.configure(foreground="red")
            return

        lines = []
        total_count = 0
        total_bytes = 0
        any_bytes_unknown = False

        for item in extract_queue:
            name = Path(item["path"]).name
            info = item.get("info")
            if info is None:
                lines.append(f"• {name}: Calculating...")
                continue
            try:
                start_sec = parse_timestamp(item.get("start", ""))
                end_sec = parse_timestamp(item.get("end", ""))
            except ValueError:
                lines.append(f"• {name}: (Invalid time range)")
                continue

            count = estimate_extraction(
                info["fps"], info["total_frames"], start_sec, end_sec, fps=fps_val, interval_frames=interval_val
            )
            total_count += count

            lines.append(f"- {name}: ~{count:,} frames")
        dedup_note = "  (maximum estimate; deduplication may reduce the final count)" if dedup_var.get() else ""
        size_text = format_size(total_bytes) + ("+" if any_bytes_unknown else "")
        total_text = f"Estimated total: ~{total_count:,} frames from {len(extract_queue)} videos{dedup_note}"
        if total_count > 3000:
            total_text += "  ⚠ Large output. Consider lowering FPS or increasing the frame interval."
            estimate_label.configure(foreground="dark orange")
        else:
            estimate_label.configure(foreground="dark green")
        estimate_total_var.set(total_text)

        estimate_detail_box.configure(state="normal")
        estimate_detail_box.delete("1.0", "end")
        estimate_detail_box.insert("1.0", "\n".join(lines))
        estimate_detail_box.configure(state="disabled")

    debounce_holder = {"id": None}

    def schedule_estimate_update(*_args):
        if debounce_holder["id"] is not None:
            try:
                root.after_cancel(debounce_holder["id"])
            except Exception:
                pass
        debounce_holder["id"] = root.after(350, update_preview_and_estimate)

    for _var in (rate_var, resize_var):
        _var.trace_add("write", schedule_estimate_update)
    mode_var.trace_add("write", lambda *_: update_preview_and_estimate())
    format_var.trace_add("write", lambda *_: update_preview_and_estimate())

    # ---  ---
    frm_progress = ttk.LabelFrame(content, text="Progress")
    frm_progress.pack(fill="x", **pad)
    current_video_var = tk.StringVar(value="")
    percent_var = tk.StringVar(value="0%")
    ttk.Label(frm_progress, textvariable=current_video_var).pack(anchor="w", padx=6, pady=(4, 0))
    progress_row = ttk.Frame(frm_progress)
    progress_row.pack(fill="x", padx=6, pady=(0, 6))
    progress_bar = ttk.Progressbar(progress_row, mode="determinate", maximum=100)
    progress_bar.pack(side="left", fill="x", expand=True)
    ttk.Label(progress_row, textvariable=percent_var, width=5).pack(side="left", padx=(8, 0))

    # --- log box ---
    frm_log = ttk.LabelFrame(content, text="Activity Log")
    frm_log.pack(fill="both", expand=True, **pad)
    log_box = tk.Text(frm_log, height=6, wrap="word", state="disabled")
    log_box.pack(fill="both", expand=True, padx=6, pady=6)

    def log(msg):
        def _do():
            log_box.configure(state="normal")
            log_box.insert("end", str(msg) + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")

        root.after(0, _do)

    def update_progress(done, total):
        pct = int(done / total * 100) if total else 0

        def _do():
            progress_bar["value"] = pct
            percent_var.set(f"{pct}%")

        root.after(0, _do)

    def update_current_video(index, total_videos, name):
        def _do():
            current_video_var.set(f"Video {index}/{total_videos}: {name}")
            progress_bar["value"] = 0
            percent_var.set("0%")

        root.after(0, _do)

    run_btn = None
    stop_btn = None
    cancel_event_holder = {"event": None}

    def set_running_state(running):
        run_btn.configure(state="disabled" if running else "normal")
        stop_btn.configure(state="normal" if running else "disabled")

    def run_extraction():
        if not extract_queue:
            messagebox.showerror("Error", "Add at least one video first.")
            return
        try:
            rate = float(rate_var.get()) if rate_var.get().strip() else None
            resize = parse_resize(resize_var.get()) if resize_var.get().strip() else None
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            return

        parsed_items = [(item["path"], None, None) for item in extract_queue]

        fps = rate if mode_var.get() == "fps" and rate else None
        interval_frames = int(rate) if mode_var.get() == "interval" and rate else None

        cancel_event = threading.Event()
        cancel_event_holder["event"] = cancel_event

        set_running_state(True)
        log_box.configure(state="normal")
        log_box.delete("1.0", "end")
        log_box.configure(state="disabled")
        progress_bar["value"] = 0
        percent_var.set("0%")
        current_video_var.set("")

        def worker():
            import os as _os
            from concurrent.futures import ThreadPoolExecutor, as_completed

            n_items = len(parsed_items)
            saved_holder = {"n": 0}
            completed_holder = {"n": 0}
            progress_lock = threading.Lock()

            def do_one(idx, path, start_sec, end_sec, progress_cb):
                name = Path(path).name
                prefixed_log = (lambda msg, _n=name: log(f"[{_n}] {msg}")) if n_items > 1 else log
                sub_out = Path(output_var.get()) / Path(path).stem
                n = extract_frames(
                    path,
                    sub_out,
                    fps=fps,
                    interval_frames=interval_frames,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    img_format=format_var.get(),
                    resize=resize,
                    prefix=prefix_var.get() or None,
                    log=prefixed_log,
                    cancel_event=cancel_event,
                    progress_callback=progress_cb,
                    dedup_enabled=dedup_var.get(),
                    dedup_threshold=get_dedup_threshold(),
                )
                with progress_lock:
                    saved_holder["n"] += n
                    completed_holder["n"] += 1
                return n

            try:
                #  thread pool  CLI/
                # (OpenCV  GIL / )
                #     thread pool  
                if n_items > 1:
                    max_workers = min(4, max(1, _os.cpu_count() or 2), n_items)
                    log(f"[INFO]  {max_workers}  ( {n_items} )")
                    current_video_var.set(f"Processing {n_items} videos in parallel...")

                    #  ( probe )
                    #  %   progress 
                    frame_counts = [
                        (item.get("info") or {}).get("total_frames", 0) for item in extract_queue
                    ]
                    total_frames_all = sum(frame_counts) or 1
                    progress_map = {i: 0 for i in range(n_items)}

                    def make_progress_cb(idx):
                        def cb(done, _total_this_video):
                            with progress_lock:
                                progress_map[idx] = done
                                current = sum(progress_map.values())
                            update_progress(current, total_frames_all)

                        return cb

                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {
                            executor.submit(do_one, i, path, s, e, make_progress_cb(i)): i
                            for i, (path, s, e) in enumerate(parsed_items)
                        }
                        for future in as_completed(futures):
                            try:
                                future.result()
                            except Exception as ex:
                                log(f"[ERROR] {ex}")
                else:
                    path, start_sec, end_sec = parsed_items[0]
                    update_current_video(1, 1, Path(path).name)
                    do_one(0, path, start_sec, end_sec, update_progress)

                total_saved = saved_holder["n"]
                log(f"\n[SUMMARY]  {total_saved}   {n_items} ")
                if cancel_event.is_set():
                    log("\n⏹ ")
                else:
                    log("\n✅ ! ")
            except Exception as e:
                log(f"\n❌ : {e}")
            finally:
                root.after(0, lambda: set_running_state(False))

        threading.Thread(target=worker, daemon=True).start()

    def stop_extraction():
        ev = cancel_event_holder["event"]
        if ev is not None:
            ev.set()
            stop_btn.configure(state="disabled")
            log("\n[...] ")

    run_btn = ttk.Button(run_btn_holder, text="▶  Extract Frames", command=run_extraction)
    run_btn.pack(side="left", expand=True, padx=(0, 4))
    stop_btn = ttk.Button(run_btn_holder, text="■  Stop", command=stop_extraction, state="disabled")
    stop_btn.pack(side="left", expand=True, padx=(4, 0))

    # ============================================================
    #  2:  (Trim)
    # ============================================================
    tab_trim = _make_tool_tab("2. ") if "trim" in visible_tools else ttk.Frame(root)
    trim_content, trim_btn_holder = make_scrollable_tab(tab_trim)

    trim_input_var = tk.StringVar()
    trim_output_var = tk.StringVar()
    trim_start_var = tk.StringVar()
    trim_end_var = tk.StringVar()
    trim_duration_var = tk.StringVar(value="")
    trim_info_holder = {"info": None}

    frm_trim_in = ttk.LabelFrame(trim_content, text="1) Select Video to Trim")
    frm_trim_in.pack(fill="x", **pad)
    frm_trim_in.columnconfigure(0, weight=1)
    ttk.Entry(frm_trim_in, textvariable=trim_input_var, width=45).grid(row=0, column=0, padx=6, pady=6, sticky="ew")

    def trim_load_info(path):
        trim_info_holder["info"] = None
        trim_duration_var.set("...")

        def worker():
            info = probe_video_info(path)

            def apply():
                trim_info_holder["info"] = info
                if info:
                    trim_duration_var.set(
                        f": {format_hms(info['duration_sec'])}  |  {info['fps']:.1f} FPS  |  {info['total_frames']} "
                    )
                else:
                    trim_duration_var.set("( — )")

            root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def trim_pick_file():
        path = filedialog.askopenfilename(
            title="Select Video to Trim",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.ts"), ("All files", "*.*")],
        )
        if path:
            trim_input_var.set(path)
            trim_load_info(path)
            if not trim_output_var.get().strip():
                p = Path(path)
                trim_output_var.set(str(p.with_name(p.stem + "_.mp4")))

    ttk.Button(frm_trim_in, text="Video File...", command=trim_pick_file).grid(row=0, column=1, padx=6)
    ttk.Label(frm_trim_in, textvariable=trim_duration_var).grid(
        row=1, column=0, columnspan=2, padx=6, pady=(0, 6), sticky="w"
    )

    frm_trim_range = ttk.LabelFrame(trim_content, text="2) Trim Range (HH:MM:SS, blank = entire clip)")
    frm_trim_range.pack(fill="x", **pad)

    def trim_set_start_beginning():
        trim_start_var.set("00:00:00")

    def trim_set_end_finish():
        info = trim_info_holder.get("info")
        if info is not None:
            trim_end_var.set(format_hms(info["duration_sec"]))
        else:
            messagebox.showinfo("End of Video", "Video duration is unknown. Please select a video first.")

    def trim_select_whole():
        trim_set_start_beginning()
        trim_set_end_finish()

    ttk.Label(frm_trim_range, text="Start:").grid(row=0, column=0, padx=(6, 2), pady=6)
    ttk.Entry(frm_trim_range, textvariable=trim_start_var, width=10).grid(row=0, column=1)
    ttk.Button(frm_trim_range, text="⏮ Start", width=10, command=trim_set_start_beginning).grid(row=0, column=2, padx=4)
    ttk.Label(frm_trim_range, text="End:").grid(row=0, column=3, padx=(12, 2))
    ttk.Entry(frm_trim_range, textvariable=trim_end_var, width=10).grid(row=0, column=4)
    ttk.Button(frm_trim_range, text="End ⏭", width=10, command=trim_set_end_finish).grid(row=0, column=5, padx=4)
    ttk.Button(frm_trim_range, text="Entire Clip", command=trim_select_whole).grid(row=0, column=6, padx=(12, 6))

    frm_trim_out = ttk.LabelFrame(trim_content, text="3) Output File (.mp4)")
    frm_trim_out.pack(fill="x", **pad)
    frm_trim_out.columnconfigure(0, weight=1)
    ttk.Entry(frm_trim_out, textvariable=trim_output_var, width=45).grid(row=0, column=0, padx=6, pady=6, sticky="ew")

    def trim_pick_output():
        path = filedialog.asksaveasfilename(
            title="Save Trimmed Video As...",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")],
            initialfile=Path(trim_output_var.get()).name if trim_output_var.get().strip() else "clip_.mp4",
        )
        if path:
            trim_output_var.set(path)

    ttk.Button(frm_trim_out, text="Choose Output Location...", command=trim_pick_output).grid(row=0, column=1, padx=6)

    trim_mode_var = tk.StringVar(value="fast")
    frm_trim_mode = ttk.LabelFrame(trim_content, text="4) Trim Mode")
    frm_trim_mode.pack(fill="x", **pad)
    ttk.Radiobutton(
        frm_trim_mode, text="Fast (FFmpeg, no re-encoding — cut may vary by up to ~2 sec near keyframes)",
        variable=trim_mode_var, value="fast",
    ).pack(anchor="w", padx=6, pady=(6, 2))
    ttk.Radiobutton(
        frm_trim_mode, text="Precise (frame-by-frame re-encoding — exact cuts, slower)",
        variable=trim_mode_var, value="accurate",
    ).pack(anchor="w", padx=6, pady=(0, 6))
    ttk.Label(
        frm_trim_mode,
        text="Note: If FFmpeg is unavailable, precise mode will be used automatically.",
    ).pack(anchor="w", padx=6, pady=(0, 6))

    frm_trim_progress = ttk.LabelFrame(trim_content, text="Progress")
    frm_trim_progress.pack(fill="x", **pad)
    trim_percent_var = tk.StringVar(value="0%")
    trim_progress_row = ttk.Frame(frm_trim_progress)
    trim_progress_row.pack(fill="x", padx=6, pady=6)
    trim_progress_bar = ttk.Progressbar(trim_progress_row, mode="determinate", maximum=100)
    trim_progress_bar.pack(side="left", fill="x", expand=True)
    ttk.Label(trim_progress_row, textvariable=trim_percent_var, width=5).pack(side="left", padx=(8, 0))

    frm_trim_log = ttk.LabelFrame(trim_content, text="Activity Log")
    frm_trim_log.pack(fill="both", expand=True, **pad)
    trim_log_box = tk.Text(frm_trim_log, height=6, wrap="word", state="disabled")
    trim_log_box.pack(fill="both", expand=True, padx=6, pady=6)

    def trim_log(msg):
        def _do():
            trim_log_box.configure(state="normal")
            trim_log_box.insert("end", str(msg) + "\n")
            trim_log_box.see("end")
            trim_log_box.configure(state="disabled")

        root.after(0, _do)

    def trim_update_progress(done, total):
        pct = int(done / total * 100) if total else 0

        def _do():
            trim_progress_bar["value"] = pct
            trim_percent_var.set(f"{pct}%")

        root.after(0, _do)

    trim_run_btn = None
    trim_stop_btn = None
    trim_cancel_holder = {"event": None}

    def trim_set_running(running):
        trim_run_btn.configure(state="disabled" if running else "normal")
        trim_stop_btn.configure(state="normal" if running else "disabled")

    def trim_run():
        if not trim_input_var.get().strip() or not Path(trim_input_var.get()).is_file():
            messagebox.showerror("Error", "Select Video to Trim")
            return
        if not trim_output_var.get().strip():
            messagebox.showerror("Error", "Please specify an output file first.")
            return
        try:
            start_sec = parse_timestamp(trim_start_var.get())
            end_sec = parse_timestamp(trim_end_var.get())
        except ValueError as e:
            messagebox.showerror("Invalid Time", str(e))
            return
        if start_sec is None and end_sec is None:
            if not messagebox.askyesno(
                "", " /Entire Clip ?"
            ):
                return

        cancel_event = threading.Event()
        trim_cancel_holder["event"] = cancel_event
        trim_set_running(True)
        trim_log_box.configure(state="normal")
        trim_log_box.delete("1.0", "end")
        trim_log_box.configure(state="disabled")
        trim_progress_bar["value"] = 0
        trim_percent_var.set("0%")

        def worker():
            try:
                ok = trim_video(
                    trim_input_var.get(),
                    trim_output_var.get(),
                    start_sec=start_sec,
                    end_sec=end_sec,
                    log=trim_log,
                    cancel_event=cancel_event,
                    progress_callback=trim_update_progress,
                    fast_mode=(trim_mode_var.get() == "fast"),
                )
                if cancel_event.is_set():
                    trim_log("\n⏹ Cancelled.")
                elif ok:
                    trim_log("\n✅ Trim completed.")
                else:
                    trim_log("\n❌ Trim failed.")
            except Exception as e:
                trim_log(f"\n❌ Error: {e}")
            finally:
                root.after(0, lambda: trim_set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    def trim_stop():
        ev = trim_cancel_holder["event"]
        if ev is not None:
            ev.set()
            trim_stop_btn.configure(state="disabled")
            trim_log("\n[...] Stopping...")

    trim_run_btn = ttk.Button(trim_btn_holder, text="✂  Trim Video", command=trim_run)
    trim_run_btn.pack(side="left", expand=True, padx=(0, 4))
    trim_stop_btn = ttk.Button(trim_btn_holder, text="■  Stop", command=trim_stop, state="disabled")
    trim_stop_btn.pack(side="left", expand=True, padx=(4, 0))

    # ============================================================
    #  3:  (Merge)
    # ============================================================
    tab_merge = _make_tool_tab("3. ") if "merge" in visible_tools else ttk.Frame(root)
    merge_content, merge_btn_holder = make_scrollable_tab(tab_merge)

    merge_files = []  #  path 
    merge_output_var = tk.StringVar()

    frm_merge_list = ttk.LabelFrame(merge_content, text="1) Video List (merged top to bottom)")
    frm_merge_list.pack(fill="x", **pad)

    merge_listbox_frame = ttk.Frame(frm_merge_list)
    merge_listbox_frame.pack(fill="x", padx=6, pady=6)
    merge_listbox = tk.Listbox(merge_listbox_frame, height=6, selectmode="extended")
    merge_listbox.pack(side="left", fill="both", expand=True)
    merge_list_scrollbar = ttk.Scrollbar(merge_listbox_frame, orient="vertical", command=merge_listbox.yview)
    merge_list_scrollbar.pack(side="left", fill="y")
    merge_listbox.configure(yscrollcommand=merge_list_scrollbar.set)

    def merge_refresh_listbox():
        merge_listbox.delete(0, "end")
        for i, p in enumerate(merge_files, start=1):
            merge_listbox.insert("end", f"{i}. {Path(p).name}")

    def merge_add_files():
        paths = filedialog.askopenfilenames(
            title="Select Videos to Merge (multiple files allowed)",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.ts"), ("All files", "*.*")],
        )
        for p in paths:
            merge_files.append(p)
        merge_refresh_listbox()

    def merge_remove_selected():
        sel = list(merge_listbox.curselection())
        for idx in reversed(sel):
            del merge_files[idx]
        merge_refresh_listbox()

    def merge_move_up():
        sel = list(merge_listbox.curselection())
        if not sel or sel[0] == 0:
            return
        for idx in sel:
            merge_files[idx - 1], merge_files[idx] = merge_files[idx], merge_files[idx - 1]
        merge_refresh_listbox()
        for idx in sel:
            merge_listbox.selection_set(idx - 1)

    def merge_move_down():
        sel = list(merge_listbox.curselection())
        if not sel or sel[-1] == len(merge_files) - 1:
            return
        for idx in reversed(sel):
            merge_files[idx + 1], merge_files[idx] = merge_files[idx], merge_files[idx + 1]
        merge_refresh_listbox()
        for idx in sel:
            merge_listbox.selection_set(idx + 1)

    def merge_clear_all():
        merge_files.clear()
        merge_refresh_listbox()

    merge_btn_row = ttk.Frame(frm_merge_list)
    merge_btn_row.pack(fill="x", padx=6, pady=(0, 6))
    ttk.Button(merge_btn_row, text="+ Add Videos...", command=merge_add_files).pack(side="left", padx=(0, 4))
    ttk.Button(merge_btn_row, text="- Remove Selected", command=merge_remove_selected).pack(side="left", padx=4)
    ttk.Button(merge_btn_row, text="▲ Move Up", command=merge_move_up).pack(side="left", padx=4)
    ttk.Button(merge_btn_row, text="▼ Move Down", command=merge_move_down).pack(side="left", padx=4)
    ttk.Button(merge_btn_row, text="Clear All", command=merge_clear_all).pack(side="left", padx=4)

    ttk.Label(
        frm_merge_list,
        text="Note: Videos with different sizes/resolutions will be adjusted to match the first file.",
    ).pack(anchor="w", padx=6, pady=(0, 6))

    frm_merge_out = ttk.LabelFrame(merge_content, text="2) Output File (.mp4)")
    frm_merge_out.pack(fill="x", **pad)
    frm_merge_out.columnconfigure(0, weight=1)
    ttk.Entry(frm_merge_out, textvariable=merge_output_var, width=45).grid(row=0, column=0, padx=6, pady=6, sticky="ew")

    def merge_pick_output():
        path = filedialog.asksaveasfilename(
            title="Save Merged Video As...",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")],
            initialfile="clip_.mp4",
        )
        if path:
            merge_output_var.set(path)

    ttk.Button(frm_merge_out, text="Choose Output Location...", command=merge_pick_output).grid(row=0, column=1, padx=6)

    frm_merge_progress = ttk.LabelFrame(merge_content, text="Progress")
    frm_merge_progress.pack(fill="x", **pad)
    merge_current_var = tk.StringVar(value="")
    ttk.Label(frm_merge_progress, textvariable=merge_current_var).pack(anchor="w", padx=6, pady=(4, 0))
    merge_percent_var = tk.StringVar(value="0%")
    merge_progress_row = ttk.Frame(frm_merge_progress)
    merge_progress_row.pack(fill="x", padx=6, pady=(0, 6))
    merge_progress_bar = ttk.Progressbar(merge_progress_row, mode="determinate", maximum=100)
    merge_progress_bar.pack(side="left", fill="x", expand=True)
    ttk.Label(merge_progress_row, textvariable=merge_percent_var, width=5).pack(side="left", padx=(8, 0))

    frm_merge_log = ttk.LabelFrame(merge_content, text="Activity Log")
    frm_merge_log.pack(fill="both", expand=True, **pad)
    merge_log_box = tk.Text(frm_merge_log, height=6, wrap="word", state="disabled")
    merge_log_box.pack(fill="both", expand=True, padx=6, pady=6)

    def merge_log(msg):
        def _do():
            merge_log_box.configure(state="normal")
            merge_log_box.insert("end", str(msg) + "\n")
            merge_log_box.see("end")
            merge_log_box.configure(state="disabled")

        root.after(0, _do)

    def merge_update_progress(done, total):
        pct = int(done / total * 100) if total else 0

        def _do():
            merge_progress_bar["value"] = pct
            merge_percent_var.set(f"{pct}%")

        root.after(0, _do)

    merge_run_btn = None
    merge_stop_btn = None
    merge_cancel_holder = {"event": None}

    def merge_set_running(running):
        merge_run_btn.configure(state="disabled" if running else "normal")
        merge_stop_btn.configure(state="normal" if running else "disabled")

    def merge_run():
        if len(merge_files) < 2:
            messagebox.showerror("Error", "Please select at least 2 videos to merge.")
            return
        if not merge_output_var.get().strip():
            messagebox.showerror("Error", "Please specify an output file first.")
            return

        cancel_event = threading.Event()
        merge_cancel_holder["event"] = cancel_event
        merge_set_running(True)
        merge_log_box.configure(state="normal")
        merge_log_box.delete("1.0", "end")
        merge_log_box.configure(state="disabled")
        merge_progress_bar["value"] = 0
        merge_percent_var.set("0%")
        merge_current_var.set(f" {len(merge_files)} ...")

        files_snapshot = list(merge_files)

        def worker():
            try:
                ok = merge_videos(
                    files_snapshot,
                    merge_output_var.get(),
                    log=merge_log,
                    cancel_event=cancel_event,
                    progress_callback=merge_update_progress,
                )
                if cancel_event.is_set():
                    merge_log("\n⏹ Cancelled.")
                elif ok:
                    merge_log("\n✅ Merge completed.")
                else:
                    merge_log("\n❌ Merge failed.")
            except Exception as e:
                merge_log(f"\n❌ Error: {e}")
            finally:
                root.after(0, lambda: merge_set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    def merge_stop():
        ev = merge_cancel_holder["event"]
        if ev is not None:
            ev.set()
            merge_stop_btn.configure(state="disabled")
            merge_log("\n[...] Stopping...")

    merge_run_btn = ttk.Button(merge_btn_holder, text="🔗  Merge Videos", command=merge_run)
    merge_run_btn.pack(side="left", expand=True, padx=(0, 4))
    merge_stop_btn = ttk.Button(merge_btn_holder, text="■  Stop", command=merge_stop, state="disabled")
    merge_stop_btn.pack(side="left", expand=True, padx=(4, 0))

    # ============================================================
    #  4:  (Images to Video)
    # ============================================================
    tab_i2v = _make_tool_tab("4. ") if "images_to_video" in visible_tools else ttk.Frame(root)
    i2v_content, i2v_btn_holder = make_scrollable_tab(tab_i2v)

    i2v_files = []  #  path 
    i2v_output_var = tk.StringVar()
    i2v_fps_var = tk.StringVar(value="25")

    frm_i2v_list = ttk.LabelFrame(i2v_content, text="1) Image List (combined top to bottom)")
    frm_i2v_list.pack(fill="x", **pad)

    i2v_listbox_frame = ttk.Frame(frm_i2v_list)
    i2v_listbox_frame.pack(fill="x", padx=6, pady=6)
    i2v_listbox = tk.Listbox(i2v_listbox_frame, height=6, selectmode="extended")
    i2v_listbox.pack(side="left", fill="both", expand=True)
    i2v_list_scrollbar = ttk.Scrollbar(i2v_listbox_frame, orient="vertical", command=i2v_listbox.yview)
    i2v_list_scrollbar.pack(side="left", fill="y")
    i2v_listbox.configure(yscrollcommand=i2v_list_scrollbar.set)

    def i2v_refresh_listbox():
        i2v_listbox.delete(0, "end")
        for i, p in enumerate(i2v_files, start=1):
            i2v_listbox.insert("end", f"{i}. {Path(p).name}")
        i2v_count_var.set(f" {len(i2v_files)} ")

    def i2v_add_files():
        paths = filedialog.askopenfilenames(
            title="Select Images to Combine (multiple files allowed)",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp"), ("All files", "*.*")],
        )
        for p in paths:
            i2v_files.append(p)
        i2v_refresh_listbox()

    def i2v_add_folder():
        folder = filedialog.askdirectory(title="Select Image Folder (sorted by filename)")
        if not folder:
            return
        found = sorted(
            p for p in Path(folder).iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not found:
            messagebox.showinfo("", "No image files found in the selected folder.")
            return
        for p in found:
            i2v_files.append(str(p))
        i2v_refresh_listbox()

    def i2v_remove_selected():
        sel = list(i2v_listbox.curselection())
        for idx in reversed(sel):
            del i2v_files[idx]
        i2v_refresh_listbox()

    def i2v_move_up():
        sel = list(i2v_listbox.curselection())
        if not sel or sel[0] == 0:
            return
        for idx in sel:
            i2v_files[idx - 1], i2v_files[idx] = i2v_files[idx], i2v_files[idx - 1]
        i2v_refresh_listbox()
        for idx in sel:
            i2v_listbox.selection_set(idx - 1)

    def i2v_move_down():
        sel = list(i2v_listbox.curselection())
        if not sel or sel[-1] == len(i2v_files) - 1:
            return
        for idx in reversed(sel):
            i2v_files[idx + 1], i2v_files[idx] = i2v_files[idx], i2v_files[idx + 1]
        i2v_refresh_listbox()
        for idx in sel:
            i2v_listbox.selection_set(idx + 1)

    def i2v_clear_all():
        i2v_files.clear()
        i2v_refresh_listbox()

    i2v_btn_row = ttk.Frame(frm_i2v_list)
    i2v_btn_row.pack(fill="x", padx=6, pady=(0, 6))
    ttk.Button(i2v_btn_row, text="+ Add Folder...", command=i2v_add_folder).pack(side="left", padx=(0, 4))
    ttk.Button(i2v_btn_row, text="+ Add Images...", command=i2v_add_files).pack(side="left", padx=4)
    ttk.Button(i2v_btn_row, text="- Remove Selected", command=i2v_remove_selected).pack(side="left", padx=4)
    ttk.Button(i2v_btn_row, text="▲ Move Up", command=i2v_move_up).pack(side="left", padx=4)
    ttk.Button(i2v_btn_row, text="▼ Move Down", command=i2v_move_down).pack(side="left", padx=4)
    ttk.Button(i2v_btn_row, text="Clear All", command=i2v_clear_all).pack(side="left", padx=4)

    i2v_count_var = tk.StringVar(value="0 images")
    ttk.Label(frm_i2v_list, textvariable=i2v_count_var).pack(anchor="w", padx=6, pady=(0, 2))
    ttk.Label(
        frm_i2v_list,
        text=": \"\"  () "
        " ",
    ).pack(anchor="w", padx=6, pady=(0, 6))

    frm_i2v_settings = ttk.LabelFrame(i2v_content, text="2) Video Settings")
    frm_i2v_settings.pack(fill="x", **pad)
    ttk.Label(frm_i2v_settings, text="FPS (frames per second):").grid(row=0, column=0, padx=6, pady=6, sticky="w")
    ttk.Entry(frm_i2v_settings, textvariable=i2v_fps_var, width=10).grid(row=0, column=1, sticky="w")

    frm_i2v_out = ttk.LabelFrame(i2v_content, text="3) Output File (.mp4)")
    frm_i2v_out.pack(fill="x", **pad)
    frm_i2v_out.columnconfigure(0, weight=1)
    ttk.Entry(frm_i2v_out, textvariable=i2v_output_var, width=45).grid(row=0, column=0, padx=6, pady=6, sticky="ew")

    def i2v_pick_output():
        path = filedialog.asksaveasfilename(
            title="Save Video As...",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")],
            initialfile=".mp4",
        )
        if path:
            i2v_output_var.set(path)

    ttk.Button(frm_i2v_out, text="Choose Output Location...", command=i2v_pick_output).grid(row=0, column=1, padx=6)

    frm_i2v_progress = ttk.LabelFrame(i2v_content, text="Progress")
    frm_i2v_progress.pack(fill="x", **pad)
    i2v_percent_var = tk.StringVar(value="0%")
    i2v_progress_row = ttk.Frame(frm_i2v_progress)
    i2v_progress_row.pack(fill="x", padx=6, pady=6)
    i2v_progress_bar = ttk.Progressbar(i2v_progress_row, mode="determinate", maximum=100)
    i2v_progress_bar.pack(side="left", fill="x", expand=True)
    ttk.Label(i2v_progress_row, textvariable=i2v_percent_var, width=5).pack(side="left", padx=(8, 0))

    frm_i2v_log = ttk.LabelFrame(i2v_content, text="Activity Log")
    frm_i2v_log.pack(fill="both", expand=True, **pad)
    i2v_log_box = tk.Text(frm_i2v_log, height=6, wrap="word", state="disabled")
    i2v_log_box.pack(fill="both", expand=True, padx=6, pady=6)

    def i2v_log(msg):
        def _do():
            i2v_log_box.configure(state="normal")
            i2v_log_box.insert("end", str(msg) + "\n")
            i2v_log_box.see("end")
            i2v_log_box.configure(state="disabled")

        root.after(0, _do)

    def i2v_update_progress(done, total):
        pct = int(done / total * 100) if total else 0

        def _do():
            i2v_progress_bar["value"] = pct
            i2v_percent_var.set(f"{pct}%")

        root.after(0, _do)

    i2v_run_btn = None
    i2v_stop_btn = None
    i2v_cancel_holder = {"event": None}

    def i2v_set_running(running):
        i2v_run_btn.configure(state="disabled" if running else "normal")
        i2v_stop_btn.configure(state="normal" if running else "disabled")

    def i2v_run():
        if len(i2v_files) < 1:
            messagebox.showerror("Error", "Please select at least 1 image first.")
            return
        if not i2v_output_var.get().strip():
            messagebox.showerror("Error", "Please specify an output file first.")
            return
        try:
            fps = float(i2v_fps_var.get())
            if fps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid FPS value (greater than 0).")
            return

        cancel_event = threading.Event()
        i2v_cancel_holder["event"] = cancel_event
        i2v_set_running(True)
        i2v_log_box.configure(state="normal")
        i2v_log_box.delete("1.0", "end")
        i2v_log_box.configure(state="disabled")
        i2v_progress_bar["value"] = 0
        i2v_percent_var.set("0%")

        files_snapshot = list(i2v_files)

        def worker():
            try:
                ok = images_to_video(
                    files_snapshot,
                    i2v_output_var.get(),
                    fps=fps,
                    log=i2v_log,
                    cancel_event=cancel_event,
                    progress_callback=i2v_update_progress,
                )
                if cancel_event.is_set():
                    i2v_log("\n⏹ Cancelled.")
                elif ok:
                    i2v_log("\n✅ Video creation completed.")
                else:
                    i2v_log("\n❌ Video creation failed.")
            except Exception as e:
                i2v_log(f"\n❌ Error: {e}")
            finally:
                root.after(0, lambda: i2v_set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    def i2v_stop():
        ev = i2v_cancel_holder["event"]
        if ev is not None:
            ev.set()
            i2v_stop_btn.configure(state="disabled")
            i2v_log("\n[...] Stopping...")

    i2v_run_btn = ttk.Button(i2v_btn_holder, text="🎬  Create Video", command=i2v_run)
    i2v_run_btn.pack(side="left", expand=True, padx=(0, 4))
    i2v_stop_btn = ttk.Button(i2v_btn_holder, text="■  Stop", command=i2v_stop, state="disabled")
    i2v_stop_btn.pack(side="left", expand=True, padx=(4, 0))

    if standalone:
        root.mainloop()
    else:
        return root


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.gui or (not args.input and len(sys.argv) == 1):
        try:
            launch_gui()
        except ImportError:
            print("[ERROR] Tkinter is unavailable on this system. Please use the CLI instead (see --help).")
            sys.exit(1)
    else:
        run_cli(args)


if __name__ == "__main__":
    main()
