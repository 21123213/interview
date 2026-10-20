"""用与 ai.ipynb 相同流程验证 hi_res + infer_table_structure。"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
load_dotenv(ROOT / ".env")
os.environ["HF_ENDPOINT"] = (
    os.getenv("HF_ENDPOINT") or "https://hf-mirror.com"
).rstrip("/")

print("HF_ENDPOINT =", os.environ["HF_ENDPOINT"])

from huggingface_hub.constants import ENDPOINT
from unstructured.partition.pdf import partition_pdf

print("huggingface_hub.ENDPOINT =", ENDPOINT)

file_path = str(ROOT / "uploads" / "Attention Is All You Need.pdf")
print("Partitioning:", file_path)

elements = partition_pdf(
    filename=file_path,
    strategy="hi_res",
    include_page_breaks=True,
    infer_table_structure=True,
    extract_image_block_types=["Image"],
    extract_image_block_to_payload=True,
    languages=["eng"],
)

tables = [e for e in elements if getattr(e, "category", None) == "Table"]
with_html = [
    e for e in tables
    if getattr(getattr(e, "metadata", None), "text_as_html", None)
]
print(f"Partitioned into {len(elements)} elements")
print(f"Tables={len(tables)}, with text_as_html={len(with_html)}")
print("SUCCESS")
