# Crescendo Backend

多轮 Crescendo 越狱评测后端。六边形（端口与适配器）架构：领域层零框架依赖，
Gemini / HuggingFace / Redis / Postgres / FastAPI 均为可替换适配器。

## 架构

```
src/crescendo/
  domain/        # 聚合根/值对象/端口接口/纯领域服务（无框架依赖）
  application/   # 用例 + AttackEngine（多模型并行 / 多轮串行的统一执行循环）
  strategies/    # AttackStrategy：gemini / template / reactive + fallback 责任链
  adapters/
    inbound/http # FastAPI 路由 + DTO + 中间件
    llm/         # GeminiAttacker（攻击者）/ HuggingFaceTarget（目标）
    judge/       # RegexJudge（可替换为 LLM judge）
    persistence/ # PostgresJobStore（真相源）+ Redis 投影 + Repository
    queue/       # InProcessQueue（默认）/ ArqQueue（独立 worker）
  infra/         # 配置 / 组合根容器 / 全局异常 / 日志
```

核心抽象：`AttackStrategy.next_prompt(ctx) -> str | None`。三种策略与未来的
单轮（Run）、解析驱动（Iterative）能力都收敛到这一接口与同一个 `AttackEngine`。

## API（前缀 `/api/v1`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/attacks` | 提交攻击：objective, models, strategy, temperature, max_turns, seed |
| GET | `/attacks/{id}` | 轮询状态与逐轮轨迹（读 Redis 投影） |
| GET | `/attacks/{id}/trace` | 从 Postgres 导出持久轨迹 |
| GET | `/models` | 可用目标模型 |
| GET | `/health` | Redis + Postgres 健康检查 |

## 本地运行

前置：Python 3.11+、本地 Postgres、本地 Redis。

```bash
cd crescendo/backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
cp .env.example .env   # 填入 GOOGLE_API_KEY / HUGGINGFACE_API_KEY / DATABASE_URL / REDIS_URL

# 开发态：ENV=dev 启动时自动建表
uvicorn crescendo.main:app --reload --app-dir src
```

无 Redis 时本地可设 `USE_MEMORY_STORE=true`（单进程、重启丢状态）。

## 任务运行时

- `TASK_QUEUE=inprocess`（默认）：在 API 进程内用 asyncio 执行，最简单。
- `TASK_QUEUE=arq`：用独立 worker 进程，重启不丢任务、可重试/扩容：

```bash
arq worker.WorkerSettings        # 另开一个进程
```

## 数据库迁移（生产）

```bash
alembic upgrade head
```

开发态 `ENV=dev` 会在启动时 `create_all` 自动建表，生产请用 Alembic。

## 测试

```bash
pytest            # 领域/策略/引擎单测，使用 fake 适配器，无需外部服务
```

## 安全与伦理

仅用于已授权的安全研究与红队评估。生产务必设置 `API_KEY`，并使用真实
Redis 与 Postgres（勿在多实例下开 `USE_MEMORY_STORE`）。
