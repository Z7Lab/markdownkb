"""lint — tiered health check for the knowledge base.

Runs four passes over the configured sources:
  - raw coverage  : raw (tier -1) files that have no corresponding
                    synthesis in the log.md of any wiki.
  - orphan        : tier-1 docs no other doc links to.
  - within-tier   : LLM-flagged contradictions between derived docs.
  - cross-tier    : LLM-flagged extension/contradiction/evolution between
                    derived and canonical docs.

Outputs a markdown report written to a user-visible location so the
report is itself a document in the knowledge base.
"""

from app.plugins.lint.router import router

__all__ = ["router"]
