# Lint Plugin

Tiered health-check for the knowledge base, modelled on Karpathy's
"wiki lint" verb (`good wiki hygiene — find stale, contradictory, or
orphaned claims and flag them for a human`) but extended for mdkb's
three-tier model (canonical / derived / raw).

Works across the whole knowledge base regardless of whether wiki_compile
is active — orphan detection, cross-tier classification, and raw-coverage
checks operate on source tiers directly, not on wiki internals.

**Feature flag:** `lint`
**Prefix:** `/api/v1/lint`

## Passes

1. **raw_coverage** *(deterministic)* — enumerates files under every
   `tier: -1` source and checks each managed wiki's `log.md` for a
   matching ingest entry. Any raw source without a synthesis anywhere
   gets flagged.

2. **orphan** *(deterministic)* — grep-style link analysis. A tier-1
   doc that no other doc links to (by filename, relative path, or any
   trailing suffix) is flagged. Auto-skips `index.md`, `log.md`, and
   `README.md` since those are navigation scaffolding.

3. **within_tier** *(LLM)* — picks up to 12 pairs of related tier-1
   docs via the retriever and asks the configured LLM whether they
   contradict. The prompt is strongly biased toward ALIGNED — only
   specifically-worded opposing claims produce a flag.

4. **cross_tier** *(LLM)* — for each tier-1 doc, finds its top tier-0
   neighbour and classifies the relationship as aligned / extension /
   contradiction / evolution. Extension and contradiction/evolution
   surface for human review; aligned pairs are not reported.

## Output

One markdown report per run, written to `{target}/lint/report-<ISO>.md`
where `{target}` is either the selected wiki's directory (when
`target_wiki` is set) or `{data_dir}/lint-reports/`. The report is
itself a markdown document — the file watcher picks it up, so lint
findings become retrievable context for future queries.

## Endpoints

| Method | Path                      | Description                     |
|--------|---------------------------|---------------------------------|
| POST   | `/api/v1/lint/run`      | Run selected passes, write report |
| GET    | `/api/v1/lint/reports`  | List previously-generated reports |

Both are gated on `plugins.lint.enabled: true`.

## Tier model

Tiers are configured per source (`settings.yaml`):

```yaml
sources:
  - path: /home/user/docs/canonical     # Tier 0 — authoritative
    writable: false                      # (infer tier: 0)
  - path: /home/user/wikis/research     # Tier 1 — derived synthesis
    writable: true                       # (infer tier: 1)
  - path: /home/user/research-inbox     # Tier -1 — raw, to be synthesized
    writable: true
    tier: -1
```

When `tier` is omitted, the default inference is: `writable: true` → 1,
`writable: false` → 0. Raw (tier -1) must be set explicitly.

## Non-goals

- Automatic link insertion (links should be human or LLM-proposed-with-approval).
- Fact-checking against external sources (breaks the local-first posture).
- Modifying any document — lint is flag-only by design.
