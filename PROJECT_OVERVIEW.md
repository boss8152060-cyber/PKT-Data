# PK Studio — ภาพรวมโปรเจ็คและข้อเสนอแนะการปรับปรุง

> จัดทำจากการตรวจโค้ด PK Studio (โฟลเดอร์ `1.3.4` → เวอร์ชันปัจจุบัน **1.3.5**, ~7,900 บรรทัด, 21 test)
> ตรวจ `core/` ละเอียด; `ui/tabs/*` และ `tools/extract_frames.py` ตรวจด้วย grep และอ่านเฉพาะช่วงที่เกี่ยวข้อง — ยังไม่เคยรันแอปกับข้อมูลจริง

---

## 1. ภาพรวมโปรเจ็ค

**เป้าหมาย:** เครื่องมือเตรียม dataset สำหรับ YOLO ของโครงการ PSU Transport (ตรวจจับ Bus, Car, Motorcycle, Person, Pickup, Side car, Truck, Van)
เน้นเฉพาะ "เตรียมข้อมูล" — การเทรน/ประเมิน/ทำนายอยู่นอกโปรแกรม (VS Code / สคริปต์เดิม)

```
DATA → LABEL → CURATE → ANALYTICS → SPLIT / EXPORT → (เทรนนอกโปรแกรม)
```

### โครงสร้างโฟลเดอร์

```text
PK Studio/                     # ← git repo (PKA-Project)
├── main.py                    # ตัวเปิดแอป
├── run_app.bat / install_and_run.bat / setup.ps1
├── requirements.txt / requirements-dev.txt
├── CLAUDE.md / PROJECT_OVERVIEW.md / plan.md / GIT_GUIDE.md
├── docs/CHANGELOG.md
├── assets/icon.ico
├── src/pk_studio/
│   ├── __init__.py            # __version__
│   ├── main.py                # เปลือกแอป: sidebar, 6 แท็บ, คีย์ลัด
│   ├── theme.py               # สี/ฟอนต์/สไตล์
│   ├── core/                  # ตรรกะที่ไม่ผูกกับ Tk (ทดสอบได้)
│   ├── ui/tabs/               # หน้าจอ Tk
│   └── tools/extract_frames.py# ดึงเฟรม + ตัด/รวมวิดีโอ (สคริปต์ใหญ่ฝัง GUI)
└── tests/
```

### โมดูลใน `core/`

| ไฟล์ | หน้าที่ |
|---|---|
| `dataset.py` | สแกนภาพ/label แบบ YOLO (key = path สัมพัทธ์, ตรวจ label ผิดรูปแบบ), `flat_name()` |
| `dataset_builder.py` | แบ่ง train/valid/test แบบ stratified + เขียน `data.yaml` (`build_yolo_dataset`) |
| `class_registry.py` | ลำดับ class (id ใน YOLO เริ่มที่ 0) |
| `smart_curator.py` | คัดภาพด้วยคะแนน rarity/diversity/difficulty/relevance (greedy) |
| `reference_labeler.py` | **Auto-Label โดยไม่มีโมเดล:** crop กรอบที่วาดไว้ แล้ว template matching หลายสเกล + NMS |
| `job_manager.py` | Job เบื้องหลัง + `UiQueue` ส่ง callback กลับ main thread |
| `fileio.py` | `atomic_write_text` |
| `project.py` | เก็บ/โหลด `project.json` (**ยังไม่ถูก UI เรียกใช้**) |

### แท็บ (UI)

| แท็บ | ไฟล์ | หน้าที่ |
|---|---|---|
| Data | `tab_data.py` → `tools/extract_frames.py` | วิดีโอ → เฟรม |
| Label | `tab_autolabeler.py` (~1,700 บรรทัด) | ตีกรอบ, จัดการ class, Auto-Label / Batch (YOLO **หรือ** reference), review |
| Curate | `tab_curator_splitter.py` | คัดภาพ, แบ่ง train/valid/test |
| Analytics | `tab_analytics.py` | สถิติ class/ตำแหน่งกรอบ/ขนาดภาพ |
| Zone | `tab_zone_editor.py` | วาด polygon zone บนเฟรมวิดีโอ (ส่งออกไปใช้กับโปรแกรมวิเคราะห์) |
| Other | `tab_other.py` | ตัด/รวมวิดีโอ, รูป → วิดีโอ |

### วิธีทำงานของ Auto-Label แบบไม่มีโมเดล (เพิ่มใน 1.3.5)

กด ⚡ Auto-Label / 🚀 Batch โดยไม่มีโมเดล → เลือก "No" → โปรแกรม crop กรอบจากภาพที่มี label (เฉลี่ยทุก class ~40 ชิ้น)
แล้วหาบริเวณคล้ายกันในภาพใหม่ (ความคล้ายขั้นต่ำเริ่มต้น 0.70) — Batch ข้ามภาพที่มี label แล้ว และไม่แก้ label เดิม
**ข้อจำกัด:** เหมาะกับกล้องนิ่ง/วัตถุหน้าตาคล้ายกัน; วัตถุหมุน/แสงต่าง/มุมมองต่างจะพลาด; เป็นตัวช่วยร่าง ต้องตรวจซ้ำ; **ยังไม่ได้ปรับค่ากับภาพจริง**

---

## 2. ข้อเสนอแนะและสถานะ (เลข # ใช้อ้างใน plan.md)

### 🔴 A. บั๊กที่กระทบข้อมูล

1. ✅ (1.3.4 → commit `b286dfd`) `build_yolo_dataset` ทับไฟล์เมื่อภาพชื่อซ้ำต่างโฟลเดอร์
2. ✅ (`b286dfd`) `copy_background=False` คัดลอกภาพไม่มี label อยู่ดี
3. ✅ (`b286dfd`) `data.yaml` ชี้ `val` ไปโฟลเดอร์ว่างเมื่อ valid = 0
4. ✅ (`b286dfd`) `DatasetScanner.scan` ล้มเมื่ออ่าน label ไม่ได้ / ไม่ตรวจ class id ติดลบและพิกัดนอก 0–1
5. ✅ (`b286dfd`, `8fb6e0b`) เขียน label/yaml ไม่ atomic
6. ✅ (`8fb6e0b`) Curate ส่งออกด้วยชื่อไฟล์เดิม → ภาพชื่อซ้ำต่างโฟลเดอร์ทับกัน
7. ✅ (`8fb6e0b`) `ui_call=self.after` ทำให้เกิด `TclError` — `on_done/on_error` ของ job ไม่เคยถึง UI
8. ✅ (`eb5830a`) worker thread เรียก Tk ตรง ๆ ในแท็บ Label/Curate → ใช้ `UiQueue`
9. ⬜ Curate ยังมี export ของตัวเอง ไม่ได้เรียก `build_yolo_dataset` (ตรรกะซ้ำสองชุด)
10. ⬜ `tools/extract_frames.py` ยังมี `threading.Thread` ดิบ 6 จุด + `root.after` จาก worker 18 จุด (ยังไม่พบบั๊กจริง ต้องทดสอบกับวิดีโอ)

### 🟠 B. คุณภาพ Auto-Label

11. ⬜ ใช้ลำดับเฟรมของวิดีโอ: tracking กรอบจากเฟรมก่อนหน้า (CSRT/KCF/optical flow) + ปุ่มคัดลอกกรอบจากเฟรมก่อน
12. ⬜ Background subtraction (MOG2) สำหรับกล้องนิ่ง + ให้ reference ตัดสิน class
13. ⬜ แสดงคะแนนความมั่นใจต่อกรอบ + คิวตรวจกรอบมั่นใจต่ำก่อน; แยกสถานะ `auto` / `reviewed`
14. ⬜ สำรอง label เดิมก่อน Batch และมีปุ่มย้อนทั้ง batch
15. ⬜ ให้ผู้ใช้เลือกกรอบตัวอย่างเอง / ORB feature matching
16. ⬜ (ระยะยาว) bootstrap เทรน YOLO เบา ๆ จาก label ที่มี แล้ววนซ้ำแบบ human-in-the-loop

### 🟡 C. ฟีเจอร์ workflow

17. ⬜ ตรวจ dataset ก่อน export (ภาพไม่มี label, กรอบหลุดขอบ, class น้อย)
18. ⬜ ใช้ `project.json` จริง (จำ dataset ล่าสุด, class order, threshold) — ตอนนี้บันทึกแบบ absolute path
19. ⬜ export COCO / Pascal VOC; augmentation ก่อน export

### 🔵 D. โครงสร้างโค้ดและการดูแลรักษา

20. ⬜ แยก `extract_frames.py` (2,400 บรรทัด, closure ยาว 286 บรรทัด) และ `tab_autolabeler.py` เป็นโมดูลเล็ก
21. ⬜ ย้ายตรรกะใน UI (remap class, save label, split) ไป `core/` + test
22. ⬜ `except Exception` 35 จุด → logging ลงไฟล์
23. ⬜ CI (GitHub Actions รัน pytest) + `ruff` + `pyproject.toml`
24. ⬜ `run_app.bat` บังคับ `py -3.12`; `setup.ps1` ตรวจลายเซ็นตัวติดตั้ง Python แล้ว (✅ `8fb6e0b`) แต่ยังไม่ได้ทดสอบจริง
25. ⬜ ทำ .exe ด้วย PyInstaller, LICENSE, คู่มือพร้อมภาพหน้าจอ

---

## 3. ลำดับงานที่แนะนำ

1. #11 tracking / คัดลอกกรอบจากเฟรมก่อน (ข้อมูลเป็นเฟรมวิดีโอ ได้ผลสูงสุด)
2. #14 สำรอง label ก่อน Batch, #22–23 logging + CI
3. #13 คะแนนความมั่นใจ + คิวตรวจ
4. #9, #21 รวมตรรกะ export / ย้ายตรรกะ UI ไป core
5. #12, #15, #16 ตามผลที่ได้จากภาพจริง

## 4. สิ่งที่ยังไม่ได้ตรวจ / ข้อควรรู้

- ยังไม่เคยเปิดแอปรันกับ dataset จริงของโครงการ (เทสต์ผ่านด้วยข้อมูลสังเคราะห์ + Tk จริงบนเครื่องนี้)
- ค่าเริ่มต้น threshold 0.70 ของ reference mode ยังไม่ได้ปรับกับภาพจริง
- `ui/tabs/tab_zone_editor.py`, `tab_analytics.py`, `tools/extract_frames.py` ยังไม่ได้อ่านทั้งไฟล์
- ไฟล์เป็น CRLF เป็นส่วนใหญ่ (Git เตือนเรื่องแปลงปลายบรรทัด ไม่กระทบการทำงาน)
