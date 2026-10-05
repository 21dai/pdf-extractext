"""Delete stored documents, for example the ones left by the load tests.

Proceso de administracion (12-Factor XII): corre con el mismo codigo y la
misma configuracion que la API, asi llega a la misma base que el servicio,
sin depender del nombre del contenedor de MongoDB ni de sus credenciales.

    python -m app.admin.clear_documents --name-regex "^(carga vu|vegeta)"
    python -m app.admin.clear_documents --all --dry-run

Dentro del stack de Docker:

    docker compose exec pdf-extractext python -m app.admin.clear_documents --all
"""

import argparse
from collections.abc import Sequence
from typing import Any

from pymongo.database import Database

from app.utils.database import get_database

COLLECTION = "documents"


def _query(name_regex: str | None) -> dict[str, Any]:
    return {"name": {"$regex": name_regex}} if name_regex else {}


def count_documents(db: Database, name_regex: str | None) -> int:
    """Count the documents that `clear_documents` would delete."""
    return db[COLLECTION].count_documents(_query(name_regex))


def clear_documents(db: Database, name_regex: str | None) -> int:
    """Delete the documents whose name matches `name_regex` (all if None).

    Returns:
        How many documents were deleted
    """
    return db[COLLECTION].delete_many(_query(name_regex)).deleted_count


def main(argv: Sequence[str] | None = None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        prog="python -m app.admin.clear_documents",
        description="Borra documentos guardados en MongoDB.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--name-regex",
        help='borra los documentos cuyo nombre coincide, ej. "^(carga vu|vegeta)"',
    )
    target.add_argument("--all", action="store_true", help="borra todos")
    parser.add_argument("--dry-run", action="store_true", help="cuenta sin borrar nada")
    args = parser.parse_args(argv)

    db = get_database()
    if args.dry_run:
        print(f"{count_documents(db, args.name_regex)} documentos se eliminarian")
    else:
        print(f"{clear_documents(db, args.name_regex)} documentos eliminados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
