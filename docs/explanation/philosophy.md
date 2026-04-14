# The Markdown-First Paradigm

> Tokens are intelligence output. They cost compute, time, and iterative refinement. Capturing them in markdown means capturing value. Losing a well-refined markdown file means losing value.

## Core Thesis

The hard part of knowledge work isn't execution — it's making decisions. What approach to take, what constraints exist, what patterns have worked before, what failed and why. Whether you're writing code, running a business, conducting research, or managing projects, the bottleneck is the same: context that lives in people's heads or scattered across old documents, never quite available when you need it.

When you capture decisions, processes, and accumulated knowledge in queryable markdown, you externalize the context that AI models would otherwise reconstruct from scratch every session.

This changes the economics of which model you need. A smaller, cheaper, local model with access to a document that describes an established pattern or a past decision doesn't need to be smart enough to figure it out. It just needs to follow it.

You're offloading reasoning into retrieval. The model doesn't need to *derive* the right approach — it needs to *find and apply* it.

## Why Markdown

Markdown isn't an arbitrary choice. It's the native communication layer between humans and AI.

It's plain text — versionable with git, diffable, greppable, immune to format lock-in. No proprietary tool required to read or write it. It survives every platform migration because there's nothing to migrate.

It's what LLMs naturally produce. Structured thinking — headings, lists, code blocks, emphasis — is markdown. Feed it back into a model and it parses cleanly with no lossy conversion. What goes in is what comes out.

It's human-readable without rendering. A markdown file opened in a text editor is immediately useful. The knowledge base serves two audiences simultaneously: AI agents querying programmatically and humans browsing, reviewing, and curating directly.

And it's composable. Markdown files can be chunked, embedded, concatenated, split, and reassembled without breaking — the ideal unit for serving partial context to models with limited context windows.

## Why Smaller Models Become Viable

Frontier models are disproportionately better at long-range reasoning, novel synthesis, and ambiguous intent. But if your markdown docs have already resolved the ambiguity — here's what we want, here's the pattern, here's the constraint — the remaining task is mechanical.

A quantized 7-8B model running locally can handle "implement this plugin following this documented pattern" far better than "figure out how plugins work in this codebase and design a new one."

You're compressing the problem space before the model sees it.

## The Compounding Knowledge Loop

Every AI interaction produces token output — intelligence that cost compute to generate. The default behavior is to let it evaporate when the session ends. The alternative: capture it as markdown, version it, feed it back into future sessions.

This creates a compounding loop:

1. Work with AI to build something or solve a problem
2. Have the agent document what was built — architecture, decisions, patterns — in markdown
3. Store those documents in a queryable knowledge base
4. Future agents query the knowledge base before acting, inheriting prior decisions
5. New work generates new documentation, enriching the base further

Patterns that took a frontier model to figure out the first time become retrievable knowledge that a local model can apply the next time.

The `wiki_compile` plugin is the concrete implementation of step 2–3 for source material that wasn't produced interactively. Point it at a research note, a meeting transcript, a vendor's whitepaper — anything dense and unstructured — and it writes a synthesized summary page into a named wiki, updates that wiki's index, appends to its log, and notes overlaps with related material already there. Wikis are named, managed targets (one per topic or domain), so the same plugin can serve a research wiki, a work wiki, and a personal wiki without their content mixing. The output is ordinary markdown, so everything downstream of it (search, chat, doc map, other agents via MCP) benefits without knowing the pages are machine-written. Raw sources stay in their own layer and are never modified. See [wiki-compile.md](wiki-compile.md) for the full architecture.

## Keeping the Knowledge Base Healthy

The compounding loop only works if what goes in is accurate and current.

**Version everything.** Markdown files are versioned alongside the code they document. History is preserved, rollback is possible.

**Update as you build.** When a feature changes, the coding agent updates the relevant markdown as part of the work. Documentation isn't a separate task — it's part of implementation.

**Don't add junk.** Not every AI output is worth saving. Stale or superseded documents get updated or removed as new work happens.

**Lint periodically.** The `lint` plugin (the third of Karpathy's three verbs) runs four passes over the configured source tiers: raw-coverage gaps, orphaned tier-1 docs, within-tier contradictions, and cross-tier tensions between derived and canonical sources. It never modifies anything — it produces a flag-only report that the file watcher picks up and adds to the retrieval corpus, so the findings themselves become queryable context. Lint works across the whole knowledge base regardless of whether wiki_compile is active.

## The Role of Frontier Models

Frontier models aren't eliminated — they're repositioned. They become the tool you reach for when the knowledge base doesn't have the answer yet: novel architecture decisions, unfamiliar problem domains, complex debugging across unfamiliar code.

But even then, the workflow captures what was learned. The frontier model's output becomes markdown, becomes retrievable knowledge, means you don't need the frontier model for that problem again.

Over time, the ratio shifts. More work falls into "well-documented patterns a local model can handle" and less into "novel problems requiring expensive inference."

## Reducing the Hurdle, Not Eliminating Difficulty

Some tasks genuinely require reasoning across large, unfamiliar codebases — tracing bugs through layers of abstraction, refactoring interconnected systems. Markdown can't fully substitute for a model that holds a lot of context and thinks hard about it.

But it dramatically reduces the hurdle. If a coding agent can query the knowledge base and find "how we built the modular plugin system" — with accurate documentation of what was actually built — the starting point is much higher. The model reasons about less because more of the context is already resolved.

## Subagent Instructions as Reusable Intelligence

Process knowledge — how to review backend code, how to structure a handoff, how to investigate a bug — can be captured as subagent instruction files: markdown documents refined through repeated use, versioned, and tested against real work.

A backend reviewer subagent instruction encodes patterns of what needs to be reviewed. Combined with a knowledge base query that retrieves relevant architecture documents, a coding agent produces work that follows established patterns without rediscovering them.

A query like "find how we do Docker and implement it on this new project" becomes viable. Retrieval finds the top documents. The agent reads them — or just the relevant chunks — and knows enough to create something good that follows patterns you've spent time establishing.

## Beyond Code

This paradigm isn't specific to software development. The core dynamic — capture intelligence output as queryable markdown, compound it over time, reduce the model capability needed — applies to any knowledge-intensive domain:

**Business operations.** Accumulated decisions, playbooks, meeting outcomes, and strategy documents become queryable institutional memory. New team members or AI assistants find "how we handle enterprise pricing negotiations" instead of reconstructing it from scratch.

**Research.** A researcher with years of accumulated notes loads them into a knowledge base. When a new paper drops — say a novel approach to modeling intercellular signaling cascades in tumor microenvironments — they load it into a scoped bucket and query: "What correlations exist between this approach and my existing work on immune checkpoint mechanisms?" Scoped searches and temporary buckets mean new material can be explored against the full body of existing work without polluting the permanent collection.

Beyond retrieval, LLMs are pattern recognition engines and markdown is their native communication format. A researcher points a model at a body of work and asks it to synthesize: find patterns, surface contradictions, identify gaps. That synthesis becomes new markdown, which goes back into the knowledge base. The next query has access not just to the original research but to the synthesized insights. Each cycle produces new intelligence that compounds — the model finds patterns you missed, writes them down, and those patterns become context for finding deeper patterns next time.

**Reviving old work.** People accumulate planning documents, strategy decks, project briefs, and research notes that sit dormant in folders. A markdown knowledge base gives them new life. Query across years of accumulated thinking with natural language — find overlaps between an old product roadmap and a current initiative, surface a planning doc from three years ago that addresses exactly the problem you're facing now, or discover that two separate projects arrived at contradictory conclusions about the same question.

**Personal knowledge management.** Anything you've learned, decided, or documented becomes retrievable context for future work — across projects, across domains, across time.

The common thread: tokens are value. Every time you interact with AI and let the output disappear, you're paying for intelligence you won't benefit from again. Capture it, version it, query it.

## Your Knowledge Stays Yours

There's a practical reason to run your own knowledge base with your own model, beyond cost and latency: privacy.

If you want AI to search, synthesize, and reason over your accumulated knowledge — your research, your business decisions, your architectural patterns, your ideas — the alternative to running it locally is handing everything to a cloud provider. Your documents go to their servers, get processed by their infrastructure, and sit in their logs. Who reviews those logs, what gets used for training, what gets retained — you don't control any of it.

A local model querying a local knowledge base keeps your thinking where it belongs. Your research stays your research. Your competitive insights stay yours. Your half-formed ideas don't become training data for a model that serves your competitors.

This matters most for the people with the most valuable knowledge to query: researchers with unpublished findings, businesses with proprietary playbooks, developers with hard-won architectural decisions. The more valuable your knowledge base, the more reason to keep it under your own roof.

## Convert, Don't Connect

A common pattern in RAG systems is to connect to external data sources — Notion, Google Drive, Slack, Confluence — and query them in place. The system becomes an adapter layer sitting on top of other people's platforms, borrowing their data at query time.

MarkdownKB deliberately doesn't do this. The design is: convert your documents to markdown and own them, rather than maintaining live connections to services you don't control.

The difference matters:

**Connecting** means your knowledge base is only as available as those services. If Notion has an outage, your knowledge base has holes. If you cancel a subscription, years of indexed knowledge disappear. If an API changes, your connector breaks. You don't own the data — you're renting access to it. You can't version it in git, you can't curate it offline, you can't hand someone a folder of files and say "here's everything I know about X."

**Converting** means you have the files. Plain text markdown on your filesystem. No API keys required to access your own knowledge. No vendor dependency. The source service could shut down tomorrow and your knowledge base is unaffected. You can version the files, diff them, edit them, move them between machines, back them up however you want.

This is why the converter plugin exists — it takes documents in any format (DOCX, PDF, HTML, EPUB, and others via Pandoc) and produces markdown files that you keep. It's not a workaround for a missing connector feature. It's the deliberate choice: your knowledge should live as files you own, not as API calls to someone else's platform.

The friction of converting is a feature. It forces a decision about what's worth keeping. Not everything in your Notion workspace belongs in your knowledge base — most of it is transient. The act of selecting, converting, and curating is what turns a pile of documents into a knowledge base worth querying.

If a document is worth querying for years, it's worth owning as a file.

Sharing follows the same principle. Buckets — scoped collections of documents — can be exported and imported as archives of plain markdown files. When you share a bucket, the recipient gets files in one expected format, not a link to a platform they need an account on. They can import the bucket into their own knowledge base, review the contents, promote what's worth keeping into their permanent collection, and discard the rest. No accounts, no permissions, no format conversion on the receiving end. Knowledge transfers as files, the same way it's stored.

Because buckets are temporary and independently searchable, they're also a tool for synthesis. Download someone's shared bucket or convert a batch of external documents into one, and you have a scoped collection you can query against your existing permanent knowledge base. Ask "what in this bucket overlaps with what I already know?" or "what's new here that I don't have?" The bucket is ephemeral — it exists for the duration of the analysis — but the insights you extract from comparing it against your own documents can be captured as new markdown and promoted into your permanent collection. Temporary input, permanent output. The bucket is disposable; the knowledge you derive from it isn't.

## The Input Side Matters More Than the Retrieval Side

Most RAG systems focus on retrieval quality — better embeddings, better chunking, better ranking. These matter, but they're secondary to the quality of what gets retrieved.

A perfect retrieval system returning vague, outdated, or poorly structured documents produces vague results. The leverage is in what goes into the knowledge base: well-structured process documents, accurate architecture descriptions, tested subagent instructions, curated findings from real work.

Retrieval is good enough that the bottleneck has shifted. Better embeddings won't save you from bad documents. The input side is where the value is created.

## The Trust Boundary

The compounding loop has a failure mode: it can compound errors.

AI-generated documentation can be confidently wrong. A model that misunderstands an architectural decision produces a clean, well-structured markdown file explaining something that isn't true. If that file enters the knowledge base unchecked, future agents retrieve it, trust it, and build on it. The error propagates.

Human review is the quality gate. Not every document needs line-by-line review, but the curation process — what goes in, what gets updated, what gets removed — determines whether the knowledge base is trustworthy.

**Treat AI-generated docs as drafts until reviewed.** The model produces the first version. A human reads it, corrects it, promotes it. Reviewing is much cheaper than writing from scratch, but the review step is non-negotiable for anything that will influence future work.

**Version history is your safety net.** When a document turns out to be wrong, you need to know when it changed and what it said before. Git gives you this for free. MarkdownKB builds it in — every mdkb-authored write is auto-committed to a per-source managed git repo, so rollback and diff are one click away in the file viewer. See [Versioning](versioning.md) for the full picture.

**Staleness is a form of inaccuracy.** A document that was correct six months ago may be actively harmful today if the system it describes has changed. Regular curation matters more than getting the initial write perfect.

## Shared Memory Across Agents

The compounding loop gets more powerful when it's not one agent reading and writing — it's many.

A knowledge base serving a single chat session is a personal notebook. A knowledge base serving multiple specialized agents — a code reviewer, a planner, a research synthesizer, a deployment assistant — is shared infrastructure. Each agent contributes knowledge from its domain and benefits from knowledge contributed by others.

The architecture is: one knowledge backend, many consumers. A human browses it in a web UI. A coding agent queries it via MCP. An orchestration system pulls context before dispatching work. A review agent checks findings against what's documented. They all read from and write to the same base, so knowledge captured by any one of them is immediately available to all.

This is where the economics compound fastest. A frontier model spends expensive tokens figuring out how your plugin system works and documents what it found. Now every other agent — including cheap local models — retrieves that documentation instead of re-deriving it. The expensive inference happens once. The cheap retrieval happens indefinitely.

## The Real Cost of Forgetting

Every AI session that ends without capturing its output is a paid invoice with no receipt. The compute was spent, the intelligence was generated, the tokens were produced — and then they disappeared. The next session starts from zero, paying again for context that already existed an hour ago.

Most people use AI like a consumable. Ask a question, get an answer, close the tab. The answer evaporates. Next time, they ask again — or worse, reconstruct from memory what the model told them, losing fidelity with every retelling.

The markdown-first paradigm treats AI output as an asset, not a consumable. Every interaction that produces useful intelligence gets captured in a format that's versionable, queryable, and feedable back into future sessions. The cost of generating that intelligence is paid once. The value compounds indefinitely.

Tokens are the most undervalued output in knowledge work today. They represent distilled reasoning that cost real compute to produce. Capturing them in markdown — the format AI natively speaks — is the simplest way to stop paying for the same intelligence twice.

## Why Retrieval Still Matters

There's a recurring claim that RAG is dead — that expanding context windows (1M+ tokens) make retrieval unnecessary. Just stuff everything in the prompt and let the model figure it out.

This is partly right, for a specific class of problem. If you're working with a single codebase that fits in a context window, a coding agent with filesystem tools doesn't need vector search to find a function definition. It can grep, read files, navigate structure directly. For structured, bounded data with predictable organization, long context and tool use are often better than retrieval.

But that's not the problem a knowledge base solves.

A knowledge base holds unstructured, natural-language documents — decisions, research notes, architecture explanations, process docs, accumulated insights across years of work. Hundreds or thousands of files, written by different people at different times, using different terminology for related concepts. When you ask "how did we handle authentication?", the answer might live in a document titled "API Security Patterns" that never uses the word "authentication." It might span three documents that each cover part of the picture. Keyword search can't find it. Filesystem navigation can't find it. But semantic search — comparing the meaning of your question against the meaning of every chunk — can.

The arguments against RAG and why they don't apply here:

**"Long context replaces retrieval."** No context window covers 900 documents totaling millions of tokens. Even if it could, sending everything on every query is expensive and slow. Retrieval narrows to the 10 relevant chunks first, then the model reasons about a focused context instead of searching a haystack. The cost difference is orders of magnitude.

**"Retrieval is lossy."** Naive retrieval is lossy. Chunking a document into 1500-token pieces and matching by vector similarity is imperfect. But the alternative — not retrieving at all and hoping the model's training data contains your specific internal knowledge — is worse. The model has never seen your architecture docs, your decision records, your process playbooks. Retrieval is the only way that knowledge reaches the model.

**"Just give the agent tools."** Tools work for structured, navigable data. Your codebase has directories, filenames, function signatures — structure that tools can traverse. Your knowledge base has "that document someone wrote about the caching incident in March." There's no directory structure that makes that findable by tool use. Semantic search over embedded chunks is the right tool for this data shape.

**"Naive RAG is dead."** This one is true. Simple chunk-and-retrieve with a single vector similarity score isn't enough. MarkdownKB uses hybrid search (vector similarity + BM25 keyword matching), configurable chunking with heading-aware splitting, score thresholds, scope-based filtering with exclude patterns, and optional deep research (multi-angle MCTS synthesis). The retrieval pipeline matters — but the answer is better retrieval, not no retrieval.

**Long context assumes cloud-scale hardware.** A 1M-token context window requires significant GPU memory just to hold the KV cache. Local models running on consumer hardware — the 8B quantized models that make local-first AI practical — typically run with 2K-8K context. Even 32K context on a local model demands substantially more RAM and slows inference. Retrieval sidesteps this entirely: embed your documents once (a CPU operation), then retrieve the 5-10 relevant chunks that fit comfortably in any context window. The model reasons over a focused, pre-filtered context instead of trying to hold your entire knowledge base in memory. This is why retrieval and local models are complementary — retrieval compensates for the smaller context window, and the smaller model compensates for retrieval's imperfection by applying reasoning to already-relevant content.

The core insight: retrieval and long context aren't competing approaches. They solve different problems. Long context is for working deeply with a bounded set of documents you've already identified. Retrieval is for finding which documents are relevant in the first place, across a collection too large to read in full. A knowledge base needs retrieval. What it does with the retrieved context — that's where model capability matters.
