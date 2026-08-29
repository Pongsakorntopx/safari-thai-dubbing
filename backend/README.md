---
title: Safari AI Thai Video Dubber API
emoji: 🎙️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🎙️ Safari AI Thai Video Dubber - Cloud Backend API

High-performance, 24/7 Cloud Backend for the **Safari Real-Time AI Thai Video Dubbing Extension**.

## ✨ Features
- 🧠 **Gemini 3.5 Flash Lite Transcreation Engine**: Cohesive 60-second narrative paragraph rewriting.
- 🚻 **Strict Gender Alignment**: Male (`ครับ/นะครับ/ผม`) and Female (`ค่ะ/นะคะ/ฉัน`) personas.
- ⚡ **Edge Neural & JaiTTS Audio Synthesis**: High-speed, crystal-clear natural Thai voices.
- 🌍 **Universal Multi-Lingual Subtitle Extraction**: English, Japanese, Korean, Chinese, Spanish, French, German, etc.
- 🚀 **REST API Endpoints**:
  - `GET /health` : Service health & available voice list
  - `POST /api/v1/transcript` : Universal multi-lingual transcript fetcher
  - `POST /api/v1/dub_batch` : 60-second batch dubbing & parallel audio synthesis
  - `POST /api/v1/dub` : Direct live dubbing

## 📡 API Usage in Safari Extension
Once deployed, copy your Space URL (e.g. `https://your-username-thai-dubber.hf.space`) and set it in the Safari Extension settings:
`backendUrl = https://your-username-thai-dubber.hf.space`
