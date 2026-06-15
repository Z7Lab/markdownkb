"""curate — corpus growth via the analyze–match–codify loop.

Turns practiced-but-uncodified patterns an agent finds in a non-canonical
source (a codebase, a bucket) into reviewed knowledge-doc drafts, with two
human gates before they graduate into the canonical corpus:

  1. per-run  — drafting is an explicit action; analysis runs freely.
  2. per-candidate — a curator reads/edits/graduates each draft by hand.

The plugin adds the one thing mdkb lacks — a draft/review store with a
status lifecycle — and composes everything else from existing pieces: the
agent does the A/B/C match via ``search``/``bucket-search``; ``graduate()``
is the gated analog of ``promote_to_wiki``. Off by default.
"""

import logging

from app.plugins.curate.router import router

FEATURE_FLAG = "curate"

__all__ = ["FEATURE_FLAG", "router", "on_startup", "on_shutdown"]

logger = logging.getLogger(__name__)


def on_startup(app) -> None:
    """Initialize CurateDB and put it on app.state for router access."""
    from app.plugins.curate.curatedb import CurateDB

    settings = app.state.settings
    app.state.curatedb = CurateDB(settings.data_directory)


def on_shutdown(app) -> None:
    """Close CurateDB connection."""
    curatedb = getattr(app.state, "curatedb", None)
    if curatedb:
        curatedb.close()
