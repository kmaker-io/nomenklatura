from contextlib import contextmanager
from functools import cache
from typing import Generator, Optional, Union

from sqlalchemy import MetaData, create_engine
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as psql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

from nomenklatura import settings

Conn = Connection
Connish = Optional[Connection]


@cache
def get_engine() -> Engine:
    return create_engine(settings.DB_URL, pool_size=settings.DB_POOL_SIZE)


@cache
def get_metadata() -> MetaData:
    return MetaData()


@contextmanager
def ensure_tx(conn: Connish = None) -> Generator[Connection, None, None]:
    if conn is not None:
        yield conn
        return
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def get_upsert_func(
    engine: Engine,
) -> Union[sqlite_insert, mysql_insert, psql_insert]:
    if engine.name == "sqlite":
        return sqlite_insert
    if engine.name == "mysql":
        return mysql_insert
    return psql_insert
