from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from app.core.config import get_settings


@contextmanager
def open_connection() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as connection:
        yield connection


def get_connection() -> Iterator[psycopg.Connection]:
    with open_connection() as connection:
        yield connection
