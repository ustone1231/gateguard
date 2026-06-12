from __future__ import annotations

from app.core.config import settings
from app.services.sql_store import SqlStore
from app.services.store import InMemoryStore


def build_store():
    if settings.storage_backend == "sql":
        return SqlStore(settings.database_url)
    return InMemoryStore()


store = build_store()
