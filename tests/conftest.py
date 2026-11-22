import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def db(tmp_path):
    """Fresh, seeded SQLite database for every test."""
    from database import connection
    from database.init_db import init_db
    connection.configure(f"sqlite:///{tmp_path / 'test.db'}")
    init_db()
    yield
    connection.get_engine().dispose()
