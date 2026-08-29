# 🇹🇭 Safari AI Thai Video Dubbing • Thai VITS & KhanomTan TTS

ระบบแปลและพากย์เสียงวิดีโอบน YouTube เป็นภาษาไทยแบบ Real-time คุณภาพสูง สำหรับ Safari (macOS / iOS) ขับเคลื่อนด้วยสถาปัตยกรรม **VITS ภาษาไทยแท้ (Variational Inference with Adversarial Learning for End-to-End TTS)** พัฒนาโดยชุมชน AI ไทย / PyThaiNLP / AIResearch
👉 **โมเดลที่รองรับ:**
1. `🇹🇭 VITS Thai Master`: โมเดล VITS เสียงไทยมาตรฐาน ควบคุมวรรณยุกต์ 5 เสียงและสระสั้น-ยาวได้ตรงตามหลักภาษาไทยแท้
2. `🧁 KhanomTan TTS v1.0 / v1.1`: โมเดลเสียงสังเคราะห์ภาษาไทยโอเพ่นซอร์ส โดย วรรณพงษ์ ภัททิยไพบูลย์ (PyThaiNLP)

---

## 🌟 จุดเด่นของระบบ (Features)

1. **End-to-End Thai VITS Models**: สถาปัตยกรรม VITS ที่เทรนบนชุดข้อมูลเสียงภาษาไทยขนาดใหญ่ (TSync2, Lotus Corpus) น้ำเสียงเป็นธรรมชาติสูงมาก
2. **Single Consistent Host Voice**: ล็อกเสียงคนเดียวตลอดทั้งคลิป 100% ไม่มีการสลับเสียงไปมาระหว่างท่อน
3. **Zero Dangling Fragments & Anti-Word Splitting**: แปลงบทสนทนาเป็นประโยคที่พูดจบสมบูรณ์ในตัวเอง ไม่ตัดคำผสมแยกออกจากกัน และไม่มีประโยคค้างคา
4. **Exact Syllable Duration Pacing**: คำนวณความเร็วและจำนวนพยางค์ภาษาไทยให้พอดีกับจังหวะเวลาของคลิปต้นฉบับอย่างแม่นยำ
5. **Monophonic Web Audio Player**: เล่นเสียงเดี่ยว ป้องกันเสียงซ้อน พร้อมปรับลดเสียงคลิปเดิม (Audio Ducking) อัตโนมัติ
6. **Hardware CoreAudio Clarity EQ**: ยกระดับความคมชัดของเสียงพูดไทยบน Safari macOS

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

```
thai-dubbing-safari/
├── backend/                  # Python FastAPI Backend (KhanomTan TTS Engine)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py         # จัดการค่า Settings, Keys & Endpoints
│   │   ├── main.py           # REST API endpoints & CORS middleware
│   │   ├── translator.py     # Gemini Localization & Complete Sentence Transcreation
│   │   ├── tts_engine.py     # KhanomTan TTS v1.0 Engine (wannaphong/khanomtan-tts-v1.0)
│   │   └── cache.py          # LRU In-Memory + SQLite Cache
│   ├── requirements.txt      # รายการ Python dependencies (pythaitts, coqui-tts)
│   ├── .env.example          # ตัวอย่างไฟล์ตั้งค่า API Key
│   └── Dockerfile            # สำหรับ Deploy ขึ้น Cloud / Docker
├── extension/                # Web Extension Source (Manifest V3)
│   ├── manifest.json         # กำหนดสิทธิ์และการทำงานของ Extension
│   ├── background.js         # Service Worker
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
