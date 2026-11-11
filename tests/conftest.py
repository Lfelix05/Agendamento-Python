"""Fixtures compartilhadas: banco em memória, cliente de teste e dados base.

Cada teste recebe um banco SQLite em memória NOVO, então nenhum teste
enxerga dados gravados por outro (isolamento).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed
from app.database import Base, get_db
from app.main import create_app
from app.models import Cliente, Profissional, Servico

# Premissa da tabela de casos de teste: segunda-feira, 16/11/2026, 08:00.
AGORA = "2026-11-16 08:00:00"

CAMADAS = ("unit", "api", "e2e")


def pytest_collection_modifyitems(items):
    """Marca cada teste com a camada (unit / api / e2e) pela pasta onde ele está.

    Assim ``pytest -m unit`` funciona sem precisar decorar teste por teste.
    """
    for item in items:
        partes = Path(item.fspath).parts
        for camada in CAMADAS:
            if camada in partes:
                item.add_marker(getattr(pytest.mark, camada))


@pytest.fixture
def relogio():
    """Congela o relógio em AGORA. ``real_asyncio`` mantém o event loop funcionando."""
    with freeze_time(AGORA, real_asyncio=True) as congelado:
        yield congelado


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",  # banco em memória
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # mesma conexão para o teste e para a API
    )
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sessao() as sessao:
        yield sessao
    engine.dispose()


@pytest.fixture
def dados(db):
    """Dados base do seed, acessíveis por nome: dados['ana'], dados['corte']..."""
    seed.popular(db)

    def por_nome(modelo, nome):
        return db.scalar(select(modelo).where(modelo.nome == nome))

    return {
        "ana": por_nome(Profissional, "Ana Lima"),
        "bruno": por_nome(Profissional, "Bruno Costa"),
        "carla": por_nome(Profissional, "Carla Dias"),
        "corte": por_nome(Servico, "Corte de cabelo"),
        "barba": por_nome(Servico, "Barba"),
        "coloracao": por_nome(Servico, "Coloração"),
        "manicure": por_nome(Servico, "Manicure"),
        "joao": por_nome(Cliente, "João Pereira"),
        "maria": por_nome(Cliente, "Maria Souza"),
        "pedro": por_nome(Cliente, "Pedro Alves"),
    }


@pytest.fixture
def client(db):
    """TestClient do FastAPI usando o banco em memória (sem subir servidor)."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    # sem "with": não dispara o lifespan, que criaria o banco em arquivo
    return TestClient(app)
