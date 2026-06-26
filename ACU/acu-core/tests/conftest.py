import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if importlib.util.find_spec("loguru") is None:

    class _DummyLogger:
        def remove(self, *args, **kwargs):
            return None

        def add(self, *args, **kwargs):
            return 1

        def debug(self, *args, **kwargs):
            return None

        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    fake_loguru = ModuleType("loguru")
    fake_loguru.logger = _DummyLogger()
    sys.modules["loguru"] = fake_loguru


def pytest_collection_modifyitems(config, items):
    """Keep real MySQL and Vector integration tests opt-in."""
    run_mysql = os.getenv("ACU_RUN_MYSQL_INTEGRATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    run_vector = os.getenv("ACU_RUN_VECTOR_INTEGRATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    skip_mysql = pytest.mark.skip(
        reason="requiere ACU_RUN_MYSQL_INTEGRATION=true y MySQL real disponible"
    )
    skip_vector = pytest.mark.skip(
        reason="requiere ACU_RUN_VECTOR_INTEGRATION=true y dependencias de faiss/chromadb"
    )

    for item in items:
        if "integration_mysql" in item.keywords and not run_mysql:
            item.add_marker(skip_mysql)
        if "integration_vector" in item.keywords and not run_vector:
            item.add_marker(skip_vector)
