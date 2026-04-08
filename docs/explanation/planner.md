# MCTS Planner

The planner uses Monte Carlo Tree Search (MCTS) to generate implementation plans grounded in your knowledge base. Instead of trial-and-error execution, it researches your docs, code, and past decisions first, evaluates multiple approaches against your patterns, and outputs one precise plan.

Think of it as the difference between a junior dev who tries things until they work, and a senior dev who studies the codebase first and gives you the exact right approach.

Requires `plugins.planner.enabled: true` in settings.

## What Is MCTS?

Monte Carlo Tree Search is a decision-making algorithm originally developed for game-playing AI (it's how AlphaGo beat world champions at Go). The core idea: instead of evaluating every possible move, build a tree of options and use repeated random sampling to figure out which branches are most promising.

In game AI, the tree represents possible moves. In mdkb's planner, the tree represents possible **implementation approaches**. Each node is a plan or sub-plan, and the algorithm explores, evaluates, and refines them:

1. **Select** — pick a node to explore using **UCB1** (Upper Confidence Bound 1). This is the key insight that makes MCTS work: it balances exploitation (revisiting approaches that scored well) against exploration (trying approaches that haven't been explored much). The formula is `score + C * sqrt(ln(parent_visits) / visits)`. The first term favors high-scoring nodes. The second term grows when a node has been visited few times relative to its siblings — giving under-explored approaches a chance even if their initial score was lower. The constant C controls the balance (higher = more exploration). Without UCB1, the algorithm would greedily chase the first good approach and miss better alternatives.

2. **Expand** — from the selected node, generate a new child: a more detailed or refined version of that approach, informed by knowledge base context.

3. **Evaluate** — score the new node on multiple dimensions (relevance to your docs, specificity, pattern alignment, actionability).

4. **Backpropagate** — update the scores of all ancestor nodes based on what was learned. A good expansion makes its parent and grandparent look better too.

Repeat this loop for N iterations. At the end, follow the highest-scoring path from root to leaf — that's your plan.

### Why MCTS Instead of a Single LLM Call?

A single "write me a plan" prompt produces one approach with no alternatives considered. MCTS generates multiple approaches, scores them against your actual documentation, iteratively refines the best ones, and discards weak branches. The result is grounded in your knowledge base rather than the LLM's generic training data.

The tradeoff is time — MCTS makes multiple LLM calls (one per expansion). A 3-approach, 3-iteration run makes roughly 6-10 LLM calls. This takes 30 seconds to a few minutes depending on model speed, but produces significantly better plans for complex requests.

## How It Works

The planner runs a 4-phase pipeline:

```
User Request
    │
    ▼
Phase 1: Research ─────────── Search KB (top_k=10)
    │
    ▼
Phase 2: Generate Approaches ─ LLM produces N distinct approaches
    │                           Each scored on 4 dimensions
    ▼
Phase 3: Iterate ──────────── UCB1 selects best approach, LLM expands
    │                           Repeat M times, score & backpropagate
    ▼
Phase 4: Extract Best Plan ── Follow highest-scoring path through tree
    │
    ▼
(Optional) Skill Reviews ──── Specialist agents review & refine plan
```

### Phase 1: Research

The retriever searches your knowledge base for documents relevant to the request. This grounds everything that follows in your actual docs and code — the planner never generates in a vacuum.

### Phase 2: Generate Approaches

The LLM generates N distinct implementation approaches (default 3). Each approach is scored on four dimensions:

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Relevance | 30% | Semantic similarity to KB content |
| Specificity | 20% | Concrete references (file paths, imports, versions) |
| Pattern matching | 30% | Alignment with your tech stack and preferences |
| Actionability | 20% | Concrete steps, action verbs, named targets |

User patterns (React, FastAPI, TypeScript, etc.) are extracted automatically from your indexed documents.

### Phase 3: Iterate

The planner uses UCB1 (Upper Confidence Bound) to balance exploration vs exploitation — it picks the most promising approach but also considers under-explored ones. Each iteration expands the selected approach into more detailed implementation steps, scores the result, and backpropagates the score up the tree.

Default: 3 iterations. Configurable via the `iterations` parameter.

### Phase 4: Extract Best Plan

The tree is traversed following the highest-scoring path from root to leaf. All node content along this path is concatenated into the final implementation plan.

## Skill Reviews

When the `agent_skills` feature flag is enabled, specialist agents can review the generated plan before it's finalized. Each skill is defined by a `SKILL.md` file that gives the LLM a specific persona and review criteria.

### Built-in Skills

| Skill | Description |
|-------|-------------|
| `security-auditor` | Reviews for OWASP Top 10, smart contract security, auth, secrets management |
| `solidity-best-practices` | Reviews Solidity patterns, gas optimization, ERC compliance, OpenZeppelin usage |

### How Reviews Work

1. Each requested skill searches the KB for relevant context
2. The LLM assumes the skill's persona and reviews the plan
3. Issues and approvals are extracted from the review
4. After all reviews, the LLM refines the original plan incorporating all feedback

### Custom Skills

Add a directory under `app/skills/builtin/` (or a custom directory) containing a `SKILL.md` file. The first non-header line becomes the skill's description. The full content is used as the LLM's system prompt during review.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/planner/plan` | Generate a plan (blocking) |
| POST | `/api/planner/plan/stream` | Stream plan generation as SSE |
| GET | `/api/planner/skills` | List available skills |

### Request Parameters

```json
{
  "request": "Build a login page using the patterns from my auth docs",
  "iterations": 3,
  "n_approaches": 3,
  "skill_names": ["security-auditor"]
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `request` | (required) | What you want to build or plan |
| `iterations` | 3 | MCTS refinement iterations (1–10) |
| `n_approaches` | 3 | Initial approaches to generate (1–10) |
| `skill_names` | none | Skills to run reviews with |

### SSE Events (streaming endpoint)

| Event | Data | Phase |
|-------|------|-------|
| `status` | `{phase, message}` | All phases |
| `approach` | `{content, score}` | After approach generation |
| `plan` | `{plan}` | Final plan extracted |
| `sources` | `{sources}` | KB files that influenced the plan |
| `tree` | `{tree}` | Full MCTS tree (for debugging) |
| `reviews` | `{reviews, refined_plan}` | After skill reviews |
| `done` | `{}` | Planning complete |

## Configuration

```yaml
plugins:
  planner:
    enabled: true           # Enable the planner tab and endpoints

core:
  agent_skills: false       # Enable skill review system
```

The planner depends on having an active LLM provider and indexed documents in the knowledge base. Planning quality scales with how much relevant content is indexed.

## Deep Research

The MCTS engine is also used by the **Deep Research** feature (`core.deep_research`), which provides multi-angle research synthesis on the Search tab. While the planner generates implementation plans, deep research focuses on comprehensive answers to complex search queries — exploring multiple angles via MCTS before synthesizing a summary. Both use the same core library (`app/planner/`) but serve different purposes. See `app/services/deep_research.py`.
