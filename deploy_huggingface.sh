#!/bin/bash
set -e

echo "=========================================================="
echo "🚀 Hugging Face Spaces Deployment Helper"
echo "=========================================================="
echo ""

if [ -z "$1" ]; then
  echo "📌 วิธีใช้งาน (Usage):"
  echo "  ./deploy_huggingface.sh <HF_SPACE_GIT_URL>"
  echo ""
  echo "ตัวอย่างเช่น (Example):"
  echo "  ./deploy_huggingface.sh https://huggingface.co/spaces/YOUR_USERNAME/thai-dubbing-api"
  echo ""
  echo "💡 ขั้นตอนการสร้าง Space บน Hugging Face (ใช้เวลา 1 นาที):"
  echo "  1. ไปที่ https://huggingface.co/new-space"
  echo "  2. ตั้งชื่อ Space เช่น 'thai-dubbing-api'"
  echo "  3. เลือก Space SDK เป็น 'Docker' (Blank template)"
  echo "  4. เลือก Public หรือ Private ตามต้องการ แล้วกด 'Create Space'"
  echo "  5. คัดลอก Git URL ของ Space มาวางในคำสั่งด้านบน"
  echo "=========================================================="
  exit 0
fi

HF_REPO_URL="$1"
TMP_DIR="/tmp/hf_thai_dub_deploy_$(date +%s)"

echo "📦 1. Cloning Hugging Face Space repository..."
git clone "$HF_REPO_URL" "$TMP_DIR"

echo "📂 2. Copying backend files to Space..."
cp -R backend/app "$TMP_DIR/"
cp backend/Dockerfile "$TMP_DIR/"
cp backend/requirements.txt "$TMP_DIR/"
cp backend/README.md "$TMP_DIR/"

cd "$TMP_DIR"
git add .
git commit -m "Deploy Safari Thai Dubbing Backend API" || true

echo "🚀 3. Pushing to Hugging Face Spaces..."
git push origin main || git push origin master

echo ""
echo "=========================================================="
echo "🎉 DEPLOYMENT INITIATED TO HUGGING FACE SPACES!"
echo "=========================================================="
echo "เมื่อ Build สำเร็จ คุณจะได้รับ Public URL เช่น:"
echo "👉 https://<YOUR_USERNAME>-<SPACE_NAME>.hf.space"
echo ""
echo "ให้นำ URL ดังกล่าวไปวางใน Safari Extension -> ฟันเฟือง (Settings) -> Backend URL ได้ทันทีครับ!"
echo "=========================================================="

rm -rf "$TMP_DIR"
