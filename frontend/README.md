# mdkb Frontend

React SPA for mdkb built with Vite, TypeScript, Shadcn/ui, and Tailwind v4.

## Development

```bash
# From the project root (starts both backend and frontend):
./run.sh

# Or frontend only:
cd frontend && npm run dev
```

Dev server runs on `http://localhost:5173` and proxies `/api` requests to the backend at `:9713` (configured in `vite.config.ts`).

## Build

```bash
cd frontend && npm run build
```

Output goes to `frontend/dist/`, which FastAPI serves as static files in production mode (`./run.sh -p`).

## Structure

```
src/
├── App.tsx              # Tab layout (Chat, Search, Planner, Graph, Browse, Settings)
├── lib/
│   ├── api.ts           # Fetch wrapper with retry + error handling + auth
│   ├── sse.ts           # POST-based SSE streaming client
│   ├── polling.ts       # Reusable polling helper for async operations
│   ├── types.ts         # Shared TypeScript types
│   ├── query-enhancement.ts  # LLM query enhancement helper
│   └── __tests__/       # Vitest unit tests
├── contexts/
│   └── navigation.ts    # Navigation context (tab switching from child components)
├── hooks/
│   ├── use-chat.ts      # Chat state + streaming
│   ├── use-search.ts    # Search state + history
│   ├── use-files.ts     # File listing + actions
│   ├── use-settings.ts  # Settings state (coordinator)
│   ├── use-provider-settings.ts   # LLM provider actions
│   ├── use-embedding-settings.ts  # Embedding model + index actions
│   ├── use-graph.ts     # Knowledge graph data + state
│   ├── use-scopes.ts    # Scope filtering
│   ├── use-index-events.ts     # SSE index event listener
│   ├── use-llm-status.ts       # LLM online/offline polling
│   ├── use-table-sort.ts       # Generic table sorting
│   ├── use-navigation.ts       # Tab navigation hook (wraps NavigationContext)
│   └── use-persisted-state.ts  # localStorage-backed state persistence
└── components/
    ├── chat/            # Chat tab components
    ├── search/          # Search tab components
    ├── graph/           # 3D knowledge graph (react-force-graph-3d)
    ├── browse/          # Browse tab components
    ├── settings/        # Settings tab components
    └── ui/              # Shadcn/ui primitives
```

## Testing

```bash
npm run test          # Run all tests once
npm run test:watch    # Watch mode
```

Tests live in `src/lib/__tests__/` and cover utilities, API client, SSE parsing, and polling.

## Stack

- **Vite** — build tool with HMR
- **React 19** — UI framework
- **TypeScript** — type safety
- **Shadcn/ui** — component library (Radix + Tailwind)
- **Tailwind CSS v4** — utility-first styling
- **Vitest** — unit testing framework
- **@tanstack/react-virtual** — list virtualization
- **react-force-graph-3d** — 3D force-directed graph (WebGL/Three.js)
