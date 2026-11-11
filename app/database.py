"""Conexão com o SQLite e fábrica de sessões.

O caminho do banco vem da variável de ambiente ``DATABASE_URL`` (padrão:
arquivo ``agendamento.db`` na raiz do projeto). Os testes de API não usam este
engine: eles criam um banco em memória isolado por teste (ver tests/conftest.py).
"""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agendamento.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
