"""记忆层：底层全量存储；进 prompt 用近 N 轮对话骨架 + 更早增量摘要。

Redis 实现见 redis_store.RedisSessionMemoryStore（compact 仍在 windowed 应用层）。
"""

from agent.memory.base import MemoryRecord, MemoryStore
from agent.memory.full_memory import FullMemoryStore
from agent.memory.summarizer import HeuristicSummarizer, LlmSummarizer
from agent.memory.windowed import SessionMemoryStore

__all__ = [
    "MemoryRecord",
    "MemoryStore",
    "FullMemoryStore",
    "SessionMemoryStore",
    "HeuristicSummarizer",
    "LlmSummarizer",
]

try:
    from agent.memory.redis_store import RedisSessionMemoryStore

    __all__.append("RedisSessionMemoryStore")
except ImportError:
    pass
