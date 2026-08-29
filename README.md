# 🐟 Safari AI Thai Video Dubbing • Fish Speech Engine

ระบบแปลและพากย์เสียงวิดีโอบน YouTube เป็นภาษาไทยแบบ Real-time คุณภาพสตูดิโอ สำหรับ Safari (macOS / iOS) ขับเคลื่อนด้วยโมเดลสังเคราะห์เสียงสังเคราะห์ **Fish Speech (LLM-based Zero-shot Neural TTS)**

---

## 🌟 จุดเด่นของระบบ (Features)

1. **Fish Speech LLM-Based Prosody**: ใช้สถาปัตยกรรม Large Language Model สร้างเสียงสังเคราะห์ภาษาไทยที่เนียน ละมุน และเป็นธรรมชาติสูงสุด ไร้รอยต่อระหว่างคำ
2. **Zero-Shot Voice Cloning**: รองรับการโคลนเสียงจากตัวอย่างเสียงภาษาไทย 5–10 วินาที เพื่อสร้างอารมณ์ คาแรคเตอร์ และน้ำเสียงที่ตรงใจ
3. **Multi-Speaker Diarization & Auto Gender Alignment**: วิเคราะห์ผู้พูดเดี่ยวหรือกลุ่มบทสนทนา แยกเพศชาย/หญิง และจัดสรรคำลงท้าย (*ครับ/ค่ะ*) ได้อย่างถูกต้องแม่นยำ
4. **Paragraph-Level Transcreation (60s Buffer)**: แปลงบทสนทนาแบบทั้งย่อหน้า ป้องกันการตัดประโยคค้างคา และซิงค์ความเร็วการพูดกับจังหวะของวิดีโอต้นฉบับ
5. **Monophonic Single-Track Playback**: ระบบเล่นเสียงเดี่ยว ป้องกันเสียงซ้อน เสียงหลอน และปรับลดเสียงคลิปเดิม (Audio Ducking) แบบสมูท
6. **Unified Safari HUD & Extension Popup**: แถบควบคุมบนวิดีโอ YouTube ใน Safari ปรับแต่งโหมดเสียง เพศ และระดับภาษาได้ทันที 1 คลิก

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
thai-dubbing-safari/
├── backend/                  # Python FastAPI Backend (Fish Speech Engine)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py         # จัดการค่า Settings, Keys & Endpoints
│   │   ├── main.py           # REST API endpoints & CORS middleware
│   │   ├── translator.py     # Gemini 2.0/3.5/3.6 Localization Engine
│   │   ├── tts_engine.py     # Fish Speech LLM Neural TTS Engine
│   │   └── cache.py          # LRU In-Memory + SQLite Cache (v17)
│   ├── requirements.txt      # รายการ Python dependencies
│   ├── .env.example          # ตัวอย่างไฟล์ตั้งค่า API Key
│   └── Dockerfile            # สำหรับ Deploy ขึ้น Cloud / Docker
├── extension/                # Web Extension Source (Manifest V3)
│   ├── manifest.json         # กำหนดสิทธิ์และการทำงานของ Extension
│   ├── background.js         # Service Worker & Multi-Endpoint Fallback
│   ├── content.js            # YouTube DOM, Monophonic Audio Scheduler & Safari HUD
│   ├── popup/
│   │   ├── popup.html        # หน้าต่างตั้งค่า UI (Dark Mode)
│   │   ├── popup.js          # จัดการ State และเชื่อมต่อ Storage
│   │   └── popup.css         # ดีไซน์สไตล์โมเดิร์น
│   └── icons/                # ไอคอนขนาด 16x16, 48x48, 128x128 px
├── convert_to_safari.sh      # สคริปต์แปลง Web Extension เข้า Xcode สำหรับ Safari
└── README.md
```

---

## 🚀 เริ่มต้นใช้งาน (Quick Start)

### 1. ติดตั้งและรัน Backend (FastAPI)

```bash
# เข้าโฟลเดอร์โปรเจกต์
cd backend

# สร้างไฟล์ .env จาก .env.example
cp .env.example .env

# ใส่ Gemini API Key ใน .env (รับฟรีได้จาก https://aistudio.google.com/)
# GEMINI_API_KEY=AIzaSy...

# รัน Server ผ่าน virtual environment
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

ตรวจสอบการทำงานของ Server ได้ที่: `http://localhost:8000/health`

---

### 2. ติดตั้ง Web Extension บน Safari (macOS)

1. ตรวจสอบว่าติดตั้ง **Xcode** จาก Mac App Store แล้ว
2. รันคำสั่งแปลง Extension:
   ```bash
   ./convert_to_safari.sh
   ```
3. เปิดโปรเจกต์ที่สร้างขึ้นในโฟลเดอร์ `xcode-wrapper/` ด้วย Xcode:
   ```bash
   open "xcode-wrapper/Thai Dubbing for Safari/Thai Dubbing for Safari.xcodeproj"
   ```
4. กด **Run (Cmd + R)** เพื่อ Build และติดตั้ง Host App
5. เปิด **Safari** -> เข้าเมนู **Settings (Cmd + ,)** -> แท็บ **Advanced** -> ติ๊กถูก **Show features for web developers**
6. ไปที่เมนูบาร์ด้านบน **Develop** -> ติ๊กถูก **Allow Unsigned Extensions**
7. ไปที่ **Safari Settings** -> แท็บ **Extensions** -> ติ๊กเปิด **Thai Dubbing for Safari**

---

### 3. ติดตั้งบน Chrome / Brave / Edge (Developer Mode)

1. เปิดเบราว์เซอร์ไปที่ `chrome://extensions` (หรือ `edge://extensions`, `brave://extensions`)
2. เปิดสวิตช์ **Developer mode** ที่มุมขวาบน
3. คลิกปุ่ม **Load unpacked**
4. เลือกโฟลเดอร์ `extension/` ในโปรเจกต์นี้

---

## 🎛️ การใช้งานบน YouTube

1. เปิดวิดีโอภาษาอังกฤษบน **YouTube**
2. กดปุ่มเปิด **Subtitles/Closed Captions (CC)** บนวิดีโอ
3. คลิกไอคอนของ **Thai Video Dubber** บนแถบเครื่องมือ:
   - สวิตช์ **ระบบพากย์เสียงไทย** (เปิด/ปิด)
   - เลือกเสียง **เปรมวดี (หญิง)** หรือ **นิวัฒน์ (ชาย)**
   - ปรับ **ระดับเสียงพากย์** และ **ระดับ Ducking** (ลดเสียงคลิปต้นฉบับ)
   - ปรับ **ความเร็วเสียงพูด** (+5% แนะนำ)
4. เมื่อซับไตเติลภาษาอังกฤษแสดงขึ้นมา ระบบจะแปลและพากย์เสียงภาษาไทยให้อัตโนมัติทันที!

---

## ☁️ การ Deploy Backend ขึ้น Cloud ฟรี (Hugging Face Spaces)

1. ไปที่ [Hugging Face Spaces](https://huggingface.co/spaces) -> สร้าง **New Space**
2. ตั้งชื่อ Space และเลือก SDK เป็น **Docker (Blank)**
3. อัปโหลดไฟล์จากโฟลเดอร์ `backend/` ขึ้นไปที่ Space Repo
4. ไปที่แท็บ **Settings** ของ Space -> ในส่วน **Variables and secrets**:
   - เพิ่ม Secret: `GEMINI_API_KEY` = ใส่ Gemini Key ของคุณ
5. เมื่อ Build เสร็จ จะได้ Public URL (เช่น `https://username-space-name.hf.space`)
6. นำ URL นี้ไปใส่ในช่อง **Backend Server URL** ใน Popup Extension เพื่อใช้งานได้ทุกที่โดยไม่ต้องเปิดเครื่องคอมฯ รัน Server

---

## 🧪 การทดสอบระบบ (Running Unit Tests)

```bash
cd backend
./venv/bin/pytest tests/
```
