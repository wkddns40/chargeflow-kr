from collections.abc import Iterator

import psycopg

from app.core.config import get_settings


def get_connection() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as connection:
        yield connection
