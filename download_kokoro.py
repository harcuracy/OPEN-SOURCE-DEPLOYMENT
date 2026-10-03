import os
import requests
from pathlib import Path

TARGET_DIR = Path("./models/kokoro")
TARGET_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    {
        "name": "kokoro-v0_19.onnx",
        "url": "https://huggingface.co/thewh1teagle/kokoro-onnx/resolve/main/kokoro-v0_19.onnx",
        "fallback": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
        "target_size": 310 * 1024 * 1024
    },
    {
        "name": "voices.json",
        "url": "https://huggingface.co/thewh1teagle/kokoro-onnx/resolve/main/voices.json",
        "fallback": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json",
        "target_size": 30 * 1024 * 1024
    }
]


def download_file(item: dict, target: Path):
    current_size = target.stat().st_size if target.exists() else 0

    if current_size >= item["target_size"] * 0.95:
        print(f"[OK] {target.name} already downloaded ({current_size // (1024*1024)} MB).")
        return

    headers = {}
    mode = "wb"
    if current_size > 0:
        headers["Range"] = f"bytes={current_size}-"
        mode = "ab"
        print(f"Resuming {target.name} from {current_size // (1024*1024)} MB...")
    else:
        print(f"Downloading {target.name} from Hugging Face...")

    try:
        resp = requests.get(item["url"], headers=headers, stream=True, timeout=120)
        resp.raise_for_status()
    except Exception as e:
        print(f"Hugging Face URL error ({e}), trying fallback...")
        resp = requests.get(item["fallback"], headers=headers, stream=True, timeout=120)
        resp.raise_for_status()

    downloaded = current_size
    with open(target, mode) as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                print(f"  -> {downloaded // (1024*1024)} MB downloaded", end="\r")

    print(f"\n[DONE] {target.name} ready ({target.stat().st_size // (1024*1024)} MB).")


if __name__ == "__main__":
    print("Kokoro Model Downloader (Hugging Face / Direct)\n")
    for it in FILES:
        download_file(it, TARGET_DIR / it["name"])
    print("\nAll Kokoro files verified!")
