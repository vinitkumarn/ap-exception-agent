import pytest

from apagent.db import SQLiteBackend
from apagent.generate import build, load_into


@pytest.fixture(scope="session")
def built():
    return build(seed=42)


@pytest.fixture(scope="session")
def dl(built, tmp_path_factory):
    """A fresh SQLite database with the seeded data, separate from data/ap.db."""
    db = SQLiteBackend(str(tmp_path_factory.mktemp("db") / "test.db"))
    load_into(db, built)
    return db


@pytest.fixture(scope="session")
def cases(built):
    from apagent.schemas import Case
    return [Case.model_validate(c) for c in built.cases]
