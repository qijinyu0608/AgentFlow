# AgentMesh Runtime Smoke Checklist

This checklist verifies backend runtime, vector retrieval, and frontend-backend integration.

## 1) Syntax check

```bash
PYTHONPYCACHEPREFIX=/tmp/agentmesh-pyc python3 -m compileall agentmesh main.py
```

Expected:
- compileall completes without errors

## 2) Start backend

```bash
python3 main.py -s -p 8001
```

## 3) Backend basic health

```bash
curl -s http://localhost:8001/api/v1/health
curl -s http://localhost:8001/api/v1/config
```

Expected:
- health returns `status=healthy`
- config returns `code=200`

## 4) Vector DB health

```bash
python3 scripts/check_vector_health.py
```

Expected:
- output contains `[ok] vector health check passed`
- no `[error]` lines

If the script reports missing coverage for the active local model, run:

```bash
python3 scripts/rebuild_memory_indices.py
```

## 5) Vector retrieval API

```bash
curl -sG "http://localhost:8001/api/v1/memory/vector-search" \
  --data-urlencode "q=test" \
  --data-urlencode "k=8" \
  --data-urlencode "min_score=0.35"
```

Expected:
- response includes `code=200`
- response includes `data.min_score`

Notes:
- under the default `local_light` profile this should work without external network once the local embedding model is available
- if the runtime falls back, task websocket `memory_precheck` should expose `status=degraded` and a `retrieval_mode`

## 6) Frontend integration

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`.

Expected:
- config page can load teams
- sending a task opens websocket and receives workflow events

## 7) WebSocket checks

When submitting a task from frontend:
- `/api/v1/task/process` should connect
- workflow stream should include:
  - `task_started`
  - `memory_precheck`
  - agent/tool events
  - `task_finished`

If `memory_precheck.status=error`, inspect:
- `meta.memory_load_error`
- `meta.vector_search_error`

If `memory_precheck.status=degraded`, inspect:
- `meta.retrieval_mode`
- `meta.active_embedding_profile`
- `meta.active_embedding_model`
