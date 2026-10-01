# Crescendo Backend

Multi-turn Crescendo jailbreak evaluation backend. Hexagonal (ports and adapters) architecture: the domain layer has zero framework dependencies; Gemini, HuggingFace, Redis, Postgres, and FastAPI are all swappable adapters.

## Architecture

```
src/crescendo/
  domain/        # Aggregates, value objects, port interfaces, pure domain services (no framework deps)
  application/   # Use cases + AttackEngine (unified loop: parallel models / serial turns)
  strategies/    # AttackStrategy: gemini / template / reactive + fallback chain
  adapters/
    inbound/http # FastAPI routes + DTOs + middleware
    llm/         # GeminiAttacker (attacker) / HuggingFaceTarget (target)
    judge/       # RegexJudge (replaceable with LLM judge)
    persistence/ # PostgresJobStore (source of truth) + Redis projection + Repository
    queue/       # InProcessQueue (default) / ArqQueue (standalone worker)
  infra/         # Config / composition root / global exceptions / logging
```

Core abstraction: `AttackStrategy.next_prompt(ctx) -> str | None`. The three strategies and future single-run (`Run`) and parse-driven (`Iterative`) capabilities all converge on this interface and the same `AttackEngine`.

## API (prefix `/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/attacks` | Submit attack: objective, models, strategy, temperature, max_turns, seed |
| GET | `/attacks/{id}` | Poll status and per-turn trace (reads Redis projection) |
| GET | `/attacks/{id}/trace` | Export persisted trace from Postgres |
| GET | `/models` | Available target models |
| GET | `/health` | Redis + Postgres health check |

## Local development

**Prerequisites:** Python 3.11+, local Postgres, local Redis.

```bash
cd crescendo/backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
cp .env.example .env   # Set GOOGLE_API_KEY / HUGGINGFACE_API_KEY / DATABASE_URL / REDIS_URL

# Dev: tables are created automatically on startup when ENV=dev
uvicorn crescendo.main:app --reload --app-dir src
```

Without Redis locally, set `USE_MEMORY_STORE=true` (single process; state is lost on restart).

## Task runtime

- `TASK_QUEUE=inprocess` (default): runs inside the API process with asyncio; simplest setup.
- `TASK_QUEUE=arq`: uses a separate worker process; tasks survive restarts and support retry/scaling:

```bash
arq worker.WorkerSettings        # Run in a separate process
```

## Database migrations (production)

```bash
alembic upgrade head
```

With `ENV=dev`, startup runs `create_all` to create tables automatically. Use Alembic in production.

## Tests

```bash
pytest            # Domain/strategy/engine unit tests with fake adapters; no external services required
```

## Security and ethics

For authorized security research and red-team evaluation only. In production, set `API_KEY` and use real Redis and Postgres (do not enable `USE_MEMORY_STORE` in multi-instance deployments).
