# travel_skill

可组合的旅游规划工具包（Cursor Skill：`.cursor/skills/travel-plan`）。

## 使用

将仓库根目录加入 `PYTHONPATH` 后：

```python
from travel_skill import TOOLS, get_weather

# model.bind_tools(TOOLS)
get_weather.invoke({"destination": "杭州", "start_date": "2026-10-01", "days": 3})
```

结构说明见 `.cursor/skills/travel-plan/STRUCTURE.md`。
