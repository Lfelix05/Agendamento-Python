"""Cria a aplicação FastAPI e registra as rotas.

Rodar localmente:  uvicorn app.main:app --reload
Documentação automática: http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import database, seed
from app.regras import ConflitoError, EstadoInvalidoError, RegraNegocioError
from app.routes import router

STATIC = Path(__file__).parent / "static"


def iniciar_banco() -> None:
    """Cria as tabelas e insere os dados de exemplo (se o banco estiver vazio)."""
    database.Base.metadata.create_all(database.engine)
    with database.SessionLocal() as db:
        seed.popular(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    iniciar_banco()
    yield


def status_http(erro: RegraNegocioError) -> int:
    """Conflitos de horário e de estado viram 409; demais regras, 400."""
    if isinstance(erro, (ConflitoError, EstadoInvalidoError)):
        return 409
    return 400


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agendamento de Serviços",
        description="API de agendamento usada no trabalho de Qualidade e Teste de Software (UNESC).",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.exception_handler(RegraNegocioError)
    async def regra_violada(_: Request, erro: RegraNegocioError):
        return JSONResponse(
            status_code=status_http(erro),
            content={"detail": erro.mensagem, "regra": erro.regra},
        )

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def pagina_inicial():
        return FileResponse(STATIC / "index.html")

    return app


app = create_app()
