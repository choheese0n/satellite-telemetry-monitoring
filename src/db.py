"""
db — PostgreSQL 연결 도우미
---------------------------------------------------
접속 정보는 환경변수로 받습니다(기본값 제공). PowerShell 예:
    $env:PGPASSWORD = "설치할때_정한_비밀번호"
    # 필요하면: $env:PGUSER, $env:PGHOST, $env:PGPORT, $env:PGDATABASE

ensure_database() 가 대상 DB(satellite)가 없으면 자동으로 만들어 줍니다.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _cfg():
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": os.getenv("PGPORT", "5432"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", "postgres"),
        "db": os.getenv("PGDATABASE", "satellite"),
    }


def _url(dbname: str) -> str:
    c = _cfg()
    return f"postgresql+psycopg2://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{dbname}"


def get_engine() -> Engine:
    """대상 데이터베이스(satellite)에 연결하는 엔진."""
    return create_engine(_url(_cfg()["db"]))


def ensure_database() -> None:
    """대상 DB가 없으면 기본 'postgres' DB에 접속해 생성한다."""
    c = _cfg()
    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": c["db"]}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{c["db"]}"'))
                print(f"    데이터베이스 '{c['db']}' 를 새로 만들었습니다.")
            else:
                print(f"    데이터베이스 '{c['db']}' 가 이미 있습니다.")
    finally:
        admin.dispose()
