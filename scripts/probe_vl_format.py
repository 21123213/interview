"""Probe DashScope VL message formats briefly."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage

# tiny 1x1 jpeg base64
TINY = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEB"
    "AQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k="
)

model = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-vl-max")
chat = ChatTongyi(model=model)

formats = {
    "openai_image_url": [
        {"type": "text", "text": "说一个字：好"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{TINY}"}},
    ],
    "dashscope_native": [
        {"image": f"data:image/jpeg;base64,{TINY}"},
        {"text": "说一个字：好"},
    ],
    "dashscope_typed": [
        {"type": "image", "image": f"data:image/jpeg;base64,{TINY}"},
        {"type": "text", "text": "说一个字：好"},
    ],
}

for name, content in formats.items():
    try:
        resp = chat.invoke([HumanMessage(content=content)])
        c = resp.content
        print(f"OK {name}: type={type(c).__name__} value={c!r}"[:200])
    except Exception as e:
        print(f"FAIL {name}: {e}")
