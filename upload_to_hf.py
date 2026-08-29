"""Upload Backend Code to Hugging Face Spaces using HfApi."""

import os
import sys
from huggingface_hub import HfApi

def main():
    if len(sys.argv) < 2:
        print("Usage: python upload_to_hf.py <repo_id> [hf_token]")
        print("Example: python upload_to_hf.py pongsakon/thai-dubbing-api hf_xxxxxx")
        sys.exit(1)

    repo_id = sys.argv[1].replace("https://huggingface.co/spaces/", "").strip().strip("/")
    token = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HF_TOKEN")

    print(f"🚀 Uploading backend files to Hugging Face Space: {repo_id} ...")
    api = HfApi(token=token)

    # 1. Upload README.md
    print("📄 Uploading README.md (Space Metadata)...")
    api.upload_file(
        path_or_fileobj="backend/README.md",
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="space",
    )

    # 2. Upload Dockerfile
    print("🐳 Uploading Dockerfile...")
    api.upload_file(
        path_or_fileobj="backend/Dockerfile",
        path_in_repo="Dockerfile",
        repo_id=repo_id,
        repo_type="space",
    )

    # 3. Upload requirements.txt
    print("📦 Uploading requirements.txt...")
    api.upload_file(
        path_or_fileobj="backend/requirements.txt",
        path_in_repo="requirements.txt",
        repo_id=repo_id,
        repo_type="space",
    )

    # 4. Upload app/ folder
    print("📂 Uploading app/ source directory...")
    api.upload_folder(
        folder_path="backend/app",
        path_in_repo="app",
        repo_id=repo_id,
        repo_type="space",
    )

    print("\n" + "="*60)
    print("🎉 UPLOAD COMPLETED SUCCESSFULLY!")
    print(f"👉 Hugging Face Space URL: https://huggingface.co/spaces/{repo_id}")
    
    # Calculate direct endpoint URL
    # format: https://<username>-<space_name>.hf.space
    parts = repo_id.split("/")
    if len(parts) == 2:
        user_name, space_name = parts
        direct_url = f"https://{user_name.lower()}-{space_name.lower().replace('_', '-')}.hf.space"
        print(f"🌐 Direct Backend API URL: {direct_url}")
    print("="*60)

if __name__ == "__main__":
    main()
