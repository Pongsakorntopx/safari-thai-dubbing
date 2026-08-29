#!/bin/bash
set -e

echo "====================================================="
echo "🚀 Deploying Thai Dubbing API to Hugging Face Spaces"
echo "   (16GB RAM + 2 vCPU Free Tier)"
echo "====================================================="

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: ./deploy_to_huggingface.sh <HF_USERNAME> <HF_WRITE_TOKEN> [SPACE_NAME]"
    echo ""
    echo "Example:"
    echo "  ./deploy_to_huggingface.sh pongsakorn hf_abc123xyz thai-dubbing-api"
    echo ""
    echo "💡 Don't have a token yet? Get your free Write Token in 10s at:"
    echo "   https://huggingface.co/settings/tokens (Create token -> Type: Write)"
    exit 1
fi

HF_USER="$1"
HF_TOKEN="$2"
SPACE_NAME="${3:-thai-dubbing-api}"

echo "📦 Preparing Space files..."
mkdir -p hf-space/app
cp -R backend/app/* hf-space/app/
cp backend/requirements.txt hf-space/

cd hf-space

if [ ! -d ".git" ]; then
    git init -b main
fi

git config user.name "$HF_USER"
git config user.email "$HF_USER@users.noreply.huggingface.co"

git add .
git commit -m "Deploy Thai Dubbing API to Hugging Face Spaces (16GB RAM)" || true

REMOTE_URL="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${SPACE_NAME}"

echo "🌐 Creating/Pushing to Hugging Face Space: ${HF_USER}/${SPACE_NAME}..."
git remote remove space 2>/dev/null || true
git remote add space "$REMOTE_URL"

git push -u space main --force

echo ""
echo "====================================================="
echo "🎉 SUCCESS! Your 16GB RAM Space is deploying on Hugging Face!"
echo ""
echo "🔗 Space Console: https://huggingface.co/spaces/${HF_USER}/${SPACE_NAME}"
echo "🌐 Direct API URL: https://${HF_USER}-${SPACE_NAME}.hf.space"
echo "====================================================="
