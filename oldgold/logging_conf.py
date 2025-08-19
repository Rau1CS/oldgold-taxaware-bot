"""Logging configuration with optional Rich support."""
import logging

try:  # pragma: no cover - optional dependency
    from rich.logging import RichHandler

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)],
    )
except Exception:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)


LOGGER = logging.getLogger("oldgold")
