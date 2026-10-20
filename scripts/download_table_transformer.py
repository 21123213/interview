"""通过 HF 国内镜像预拉 table-transformer 到本地缓存。"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
os.environ["HF_ENDPOINT"] = (
    os.getenv("HF_ENDPOINT") or "https://hf-mirror.com"
).rstrip("/")

print("HF_ENDPOINT =", os.environ["HF_ENDPOINT"])

from huggingface_hub import hf_hub_download
from huggingface_hub.constants import ENDPOINT

print("huggingface_hub.ENDPOINT =", ENDPOINT)

repo = "microsoft/table-transformer-structure-recognition"
for fn in ("config.json", "preprocessor_config.json", "model.safetensors"):
    path = hf_hub_download(repo, fn)
    size_mb = Path(path).stat().st_size / (1024 * 1024)
    print(f"OK {fn}: {size_mb:.2f} MB -> {path}")

print("DONE")
