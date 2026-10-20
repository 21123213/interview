import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "ai.ipynb"
nb = json.loads(p.read_text(encoding="utf-8"))

nb["cells"][1]["source"] = [
    "def partition_document(file_path: str):\n",
    '    """与 backend file_processing._parse_pdf(hi_res) 对齐的解析测试。"""\n',
    '    print(f"Partitioning document: {file_path}")\n',
    '    print(f"HF_ENDPOINT={os.environ.get(\'HF_ENDPOINT\')}")\n',
    "    elements = partition_pdf(\n",
    "        filename=file_path,\n",
    '        strategy="hi_res",\n',
    "        include_page_breaks=True,\n",
    "        infer_table_structure=True,  # 正确参数名（会触发 table-transformer 下载/缓存）\n",
    '        extract_image_block_types=["Image"],\n',
    "        extract_image_block_to_payload=True,\n",
    '        languages=["eng"],\n',
    "    )\n",
    '    print(f"Partitioned document into {len(elements)} elements.")\n',
    '    tables = [e for e in elements if getattr(e, "category", None) == "Table"]\n',
    "    with_html = [\n",
    "        e for e in tables\n",
    '        if getattr(getattr(e, "metadata", None), "text_as_html", None)\n',
    "    ]\n",
    '    print(f"Tables={len(tables)}, with text_as_html={len(with_html)}")\n',
    "    return elements\n",
    "\n",
    'file_path = "./uploads/Attention Is All You Need.pdf"\n',
    "elements = partition_document(file_path)\n",
]
nb["cells"][1]["outputs"] = []
nb["cells"][1]["execution_count"] = None
p.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("updated", p)
