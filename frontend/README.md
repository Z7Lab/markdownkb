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
├── App.tsx              # Tab layout (Chat, Search, Browse, Settings)
├── lib/
│   ├── api.ts           # Fetch wrapper with retry + error handling
│   ├── sse.ts           # POST-based SSE streaming client
│   ├── types.ts         # Shared TypeScript types
│   └── query-enhancement.ts  # LLM query enhancement helper
├── contexts/
│   └── navigation.ts    # Navigation context (tab switching from child components)
├── hooks/
│   ├── use-chat.ts      # Chat state + streaming
│   ├── use-search.ts    # Search state + history
│   ├── use-files.ts     # File listing + actions
│   ├── use-settings.ts  # Settings state
│   ├── use-llm-status.ts       # LLM online/offline polling
│   ├── use-table-sort.ts       # Generic table sorting
│   ├── use-navigation.ts       # Tab navigation hook (wraps NavigationContext)
│   └── use-persisted-state.ts  # localStorage-backed state persistence
└── components/
    ├── chat/            # Chat tab components
    ├── search/          # Search tab components
    ├── browse/          # Browse tab components
    ├── settings/        # Settings tab components
    └── ui/              # Shadcn/ui primitives
```

## Stack

- **Vite** — build tool with HMR
- **React 19** — UI framework
- **TypeScript** — type safety
- **Shadcn/ui** — component library (Radix + Tailwind)
- **Tailwind CSS v4** — utility-first styling
