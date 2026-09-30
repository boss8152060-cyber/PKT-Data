# plan.md — แผนงานและสถานะ (PK Studio)

> อัปเดตไฟล์นี้ทุกครั้งที่งานเปลี่ยนสถานะ (กฎอยู่ใน `CLAUDE.md`)
> รายละเอียดของแต่ละข้อ (เลข #) ดูใน `PROJECT_OVERVIEW.md` หัวข้อ 2
> สถานะ: `[ ]` รอทำ · `[~]` กำลังทำ · `[x]` เสร็จ (ระบุเวอร์ชัน/วันที่)

## ▶ ทำต่อจากตรงนี้

- **สถานะปัจจุบัน:** เวอร์ชัน 1.3.5 — แก้บั๊ก core/UI job แล้ว, Auto-Label/Batch ทำงานได้โดยไม่มีโมเดล (reference boxes), มี 21 test, push ขึ้น GitHub แล้ว, เอกสารครบ
- **ขั้นถัดไป:** ให้ผู้ใช้ลองเปิดแอปกับภาพจริง 20–30 ภาพ (ทั้ง Auto-Label เดี่ยวและ Batch โหมด No) แล้วรายงานว่ากรอบเกิน/ขาดแบบไหน → ปรับ threshold/วิธี; จากนั้นเริ่มเฟส 1 ข้อ 1.1
- **commit ถัดไปควรเป็น:** `PK Studio 1.3.6: ...` (ดูรูปแบบใน `CLAUDE.md`)
- **Remote:** `origin` = https://github.com/boss8152060-cyber/PKA-Project.git (branch `main`)
- **Backup:** `PSU Transport Project 2026\Backups\` (ต้นฉบับ `PK_Program_backup_2026-09-30.zip`)

## เฟส 0 — เตรียมงาน

- [x] 0.1 สำรองโฟลเดอร์ PK Program ทั้งหมดเป็น zip (2026-09-30)
- [x] 0.2 `git init` + `.gitignore` + remote PKA-Project + push แรก (2026-09-30, `b286dfd`)
- [x] 0.3 ตรวจโค้ดรอบแรก (รายการใน `PROJECT_OVERVIEW.md` หัวข้อ 2)
- [x] 0.4 เขียน CLAUDE.md / PROJECT_OVERVIEW.md / plan.md / GIT_GUIDE.md ตามแนวของโปรเจ็ค Run (2026-09-30)

## เฟส 1 — ยืนยันและปรับ Auto-Label แบบไม่มีโมเดล (1.3.5)

- [x] 1.0 สร้าง `core/reference_labeler.py` + ต่อ UI (Auto-Label เดี่ยว + Batch) + test (1.3.5, `eb5830a`)
- [ ] 1.1 (#13-สำรอง) สำรอง label เดิมก่อน Batch + ปุ่มย้อนทั้ง batch
- [ ] 1.2 ทดสอบกับภาพจริง 20–30 ภาพ, ปรับ threshold/จำนวน reference/สเกล ตามผล (ต้องมีผู้ใช้รายงาน)
- [ ] 1.3 (#13) แสดงคะแนนความมั่นใจต่อกรอบ (สี) + สถานะ `auto`/`reviewed`

## เฟส 2 — ใช้ข้อมูลลำดับเฟรมจากวิดีโอ

- [ ] 2.1 (#11) ปุ่มคัดลอกกรอบจากเฟรมก่อนหน้า (คีย์ลัด Ctrl+D)
- [ ] 2.2 (#11) Tracking กรอบจากเฟรมก่อนหน้าไปเฟรมถัดไป (CSRT/KCF/optical flow) เป็นโหมดที่สามของ Auto-Label
- [ ] 2.3 (#12) Background subtraction สำหรับกล้องนิ่ง (ทดลอง)
- [ ] 2.4 (#15) เลือกกรอบตัวอย่างเอง / ORB (ถ้า 1.2 พบว่าจำเป็น)

## เฟส 3 — เสถียรภาพและคุณภาพโค้ด

- [ ] 3.1 (#23) GitHub Actions รัน pytest + `ruff` + `pyproject.toml`
- [ ] 3.2 (#22) เปลี่ยน `except Exception` เป็น logging ลงไฟล์
- [ ] 3.3 (#9) ให้แท็บ Curate เรียก `build_yolo_dataset` แทนโค้ดส่งออกของตัวเอง
- [ ] 3.4 (#10) ย้าย thread ดิบใน `extract_frames.py` ไปใช้ `JobManager`/`UiQueue` (ต้องทดสอบด้วยวิดีโอจริง)
- [ ] 3.5 (#20, #21) แยก `extract_frames.py` / `tab_autolabeler.py`, ย้ายตรรกะ UI ไป `core/` พร้อม test

## เฟส 4 — ฟีเจอร์ workflow

- [ ] 4.1 (#17) ตรวจ dataset ก่อน export
- [ ] 4.2 (#18) ใช้ `project.json` (path สัมพัทธ์) จำการตั้งค่า
- [ ] 4.3 (#19) export COCO/VOC, augmentation
- [ ] 4.4 (#16) bootstrap เทรน YOLO เบา ๆ (ต้องมี GPU + ultralytics)
- [ ] 4.5 (#25) .exe, LICENSE, คู่มือพร้อมภาพหน้าจอ

## บันทึกความคืบหน้า (ใหม่สุดอยู่บน)

| วันที่ | สิ่งที่ทำ | ไฟล์ที่เกี่ยวข้อง | ค้างอยู่ |
|---|---|---|---|
| 2026-09-30 | เพิ่มเอกสารควบคุมงาน (CLAUDE/OVERVIEW/plan/GIT_GUIDE) ตามแนว Run | `CLAUDE.md`, `PROJECT_OVERVIEW.md`, `plan.md`, `GIT_GUIDE.md` | ลองแอปกับภาพจริง |
| 2026-09-30 | 1.3.5: Auto-Label/Batch ไม่ต้องมีโมเดล; `UiQueue` แทน `after` จาก worker | `core/reference_labeler.py`, `core/job_manager.py`, `ui/tabs/tab_autolabeler.py`, `tab_curator_splitter.py` | ปรับ threshold กับภาพจริง |
| 2026-09-30 | แก้ callback ของ job (`ui_call=self.after` → TclError), Curate export ชื่อซ้ำ, `greedy_select` เร็วขึ้น, `setup.ps1` ตรวจลายเซ็น | `core/job_manager.py`, `core/smart_curator.py`, `setup.ps1` | — |
| 2026-09-30 | แก้บั๊ก builder/scanner, atomic write, เพิ่ม requirements + test; push แรก | `core/dataset*.py`, `core/fileio.py`, `tests/` | — |
