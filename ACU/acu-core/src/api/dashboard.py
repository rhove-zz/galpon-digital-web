"""Dashboard template loader for ACU monitoring."""

from functools import lru_cache
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
DASHBOARD_TEMPLATE = TEMPLATE_DIR / "dashboard.html"


@lru_cache(maxsize=1)
def get_dashboard_html() -> str:
    """Return the ACU monitoring dashboard HTML template."""
    return DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
