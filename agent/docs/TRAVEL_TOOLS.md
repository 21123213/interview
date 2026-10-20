# Agent 旅游与通用检索工具

## 按 Skill 注册（每次请求）

工具表由 `build_registry_for_input(user_input)` 按 skill 组装，**不是**启动时全量注册。

| 场景 | 注册工具 |
|------|----------|
| 始终 | `calculator` / `get_time` / `echo` / `io_ping` / `web_search` |
| 有 XHS 目录 | 另加 `xhs_search`（搜索并自动拉若干笔记正文；≤50 字丢弃） |
| 旅游（skill=`travel`） | 另加 `get_culture`、`get_weather`、`geocode_places`、`build_route`、`search_stay`、`plan_transport` |

检测：`agent/skills/loader.py` → `resolve_skills` / `looks_like_travel`。  
日志：transcript 首条 `phase=tool_registry`，以及 `react.run` / `plan_execute.run` span attrs。

### 旅游专用说明

| 工具 | 说明 |
|------|------|
| `xhs_search` | 关键词 → 笔记列表 + 正文（线路由主模型按 skill 提炼） |
| `get_culture` | 闭馆/活动原始检索；`start_date` + 可选 `season` |
| `get_weather` | 天气预报 |
| `geocode_places` | 地名转坐标 |
| `build_route` | 编每日行程 |
| `search_stay` | 酒店 |
| `plan_transport` | 交通接驳（`hotel` 用 search_stay 返回对象） |

> 已移除 `search_play`（原：小红书长文 + 工具内 LLM 抽线路，易超时）。

## Skill 注入

路径：`agent/skills/travel/SKILL.md`  
旅游需求时，ReAct / Planner 的 system prompt 会追加该技能说明（与工具注册同一判定）。

## 环境变量

- `BOCHA_API_KEY` / `BOCHA_API_BASE`
- `XHS_SKILLS_ROOT`（默认仓库内 `xiaohongshu-skills-main`）
- `AGENT_XHS_SEARCH_DETAIL_LIMIT`（`xhs_search` 自动拉正文条数，默认 5）
- `XHS_NOTE_MIN_CHARS`（默认 50：正文须 **超过** 该字数才保留）
- 以及天气/高德/道旅等既有配置（见根 `.env`）

## 小红书前置

Chrome 启用 XHS Bridge 扩展并登录小红书。
