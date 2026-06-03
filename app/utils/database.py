"""MongoDB connection helpers and database bootstrap."""

from functools import lru_cache
from typing import Generator

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """Create and cache a MongoDB client."""
    if settings.database_url.startswith("mongomock://"):
        try:
            import mongomock
        except ImportError as exc:
            raise RuntimeError(
                "mongomock is required when DATABASE_URL starts with mongomock://"
            ) from exc
        return mongomock.MongoClient()

    return MongoClient(
        settings.database_url,
        serverSelectionTimeoutMS=settings.database_timeout_ms,
    )


def reset_client() -> None:
    """Clear the cached client instance."""
    get_client.cache_clear()


def get_database() -> Database:
    """Return the configured MongoDB database."""
    return get_client()[settings.database_name]


def get_db() -> Generator[Database, None, None]:
    """Yield the configured MongoDB database."""
    yield get_database()


def create_tables() -> None:
    """Initialize collections and indexes."""
    try:
        documents = get_database()["documents"]
        documents.create_index([("id", ASCENDING)], unique=True)
        documents.create_index([("checksum", ASCENDING)], unique=True)
        documents.create_index([("file_path", ASCENDING)], unique=True)
        documents.create_index([("name", ASCENDING)])

        counters = get_database()["counters"]
        counters.update_one(
            {"_id": "document_id"},
            {"$setOnInsert": {"value": 0}},
            upsert=True,
        )
    except PyMongoError as exc:
        raise RuntimeError(
            "No se pudo conectar a MongoDB. "
            "Verifica DATABASE_URL o inicia el servidor antes de levantar la API."
        ) from exc


def drop_tables() -> None:
    """Drop the configured database."""
    client = get_client()
    client.drop_database(settings.database_name)
