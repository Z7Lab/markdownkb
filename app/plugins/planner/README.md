# Planner Plugin

MCTS (Monte Carlo Tree Search) based implementation plan generation with agent skills and scope filtering.

**Feature flag:** `planner`
**Prefix:** `/api/v1/planner`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/planner/plan` | Generate an implementation plan using MCTS |
| POST | `/api/v1/planner/plan/stream` | Stream plan generation progress as SSE |
| GET | `/api/v1/planner/plans` | List saved plans |
| POST | `/api/v1/planner/plans` | Save a plan |
| GET | `/api/v1/planner/plans/{id}` | Load a saved plan |
| DELETE | `/api/v1/planner/plans/{id}` | Delete a saved plan |
| GET | `/api/v1/planner/skills` | List available agent skills |

## Plan Request

```json
{
  "request": "Build a REST API for user management",
  "iterations": 5,
  "n_approaches": 3,
  "skill_names": ["python", "api-design"],
  "scope_id": "optional-scope-id"
}
```

## Dependencies

- `app.rag.retriever` — context retrieval for plan generation
- `app.services.planner_service` — MCTS planning engine and skill system
- `app.storage.plandb` — plan persistence
- `app.storage.scopedb` — scope resolution
