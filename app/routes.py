"""Endpoints da API. A lógica de negócio fica em ``regras.py``; aqui só há
consulta ao banco, chamada das regras e gravação do resultado."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import regras
from app.database import get_db
from app.models import Agendamento, Cliente, Profissional, Servico
from app.regras import Status
from app.schemas import (
    AgendamentoCreate,
    AgendamentoDetalhadoOut,
    AgendamentoOut,
    ClienteCreate,
    ClienteOut,
    DisponibilidadeOut,
    ErroOut,
    ProfissionalOut,
    ServicoOut,
)

router = APIRouter()

ERROS = {
    400: {"model": ErroOut, "description": "Regra de negócio violada"},
    404: {"model": ErroOut, "description": "Registro não encontrado"},
    409: {"model": ErroOut, "description": "Conflito de horário ou de estado"},
}


def agora() -> datetime:
    """Único ponto que lê o relógio. Nos testes, o freezegun controla este valor."""
    return datetime.now()


def _buscar(db: Session, modelo, id_: int, nome: str):
    obj = db.get(modelo, id_)
    if obj is None:
        raise HTTPException(404, f"{nome} {id_} não encontrado.")
    return obj


def _agenda_do_dia(db: Session, dia: date, **filtro) -> list[Agendamento]:
    inicio_dia = datetime.combine(dia, datetime.min.time())
    stmt = (
        select(Agendamento)
        .filter_by(**filtro)
        .where(Agendamento.inicio >= inicio_dia, Agendamento.inicio < inicio_dia + timedelta(days=1))
        .order_by(Agendamento.inicio)
    )
    return list(db.scalars(stmt))


# ------------------------------------------------------------------ cadastros
@router.get("/profissionais", response_model=list[ProfissionalOut])
def listar_profissionais(db: Session = Depends(get_db)):
    return db.scalars(select(Profissional).order_by(Profissional.nome)).all()


@router.get("/servicos", response_model=list[ServicoOut])
def listar_servicos(db: Session = Depends(get_db)):
    return db.scalars(select(Servico).order_by(Servico.nome)).all()


@router.get("/clientes", response_model=list[ClienteOut])
def listar_clientes(db: Session = Depends(get_db)):
    return db.scalars(select(Cliente).order_by(Cliente.nome)).all()


@router.post("/clientes", response_model=ClienteOut, status_code=201, responses=ERROS)
def criar_cliente(dados: ClienteCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Cliente).where(Cliente.telefone == dados.telefone)) is not None:
        raise HTTPException(409, f"Já existe um cliente com o telefone {dados.telefone}.")
    cliente = Cliente(nome=dados.nome, telefone=dados.telefone)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


# ------------------------------------------------------------------ agendamentos
@router.post("/agendamentos", response_model=AgendamentoOut, status_code=201, responses=ERROS)
def criar_agendamento(dados: AgendamentoCreate, db: Session = Depends(get_db)):
    cliente = _buscar(db, Cliente, dados.cliente_id, "Cliente")
    profissional = _buscar(db, Profissional, dados.profissional_id, "Profissional")
    servico = _buscar(db, Servico, dados.servico_id, "Serviço")

    dia = dados.inicio.date()
    fim = regras.validar_novo_agendamento(
        inicio=dados.inicio,
        servico_id=servico.id,
        duracao_min=servico.duracao_min,
        profissional=profissional.dados_regras(),
        agenda_profissional=[a.periodo() for a in _agenda_do_dia(db, dia, profissional_id=profissional.id)],
        agenda_cliente=[a.periodo() for a in _agenda_do_dia(db, dia, cliente_id=cliente.id)],
        agora=agora(),
    )

    agendamento = Agendamento(
        cliente_id=cliente.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        inicio=dados.inicio,
        fim=fim,
        status=Status.ATIVO.value,
    )
    db.add(agendamento)
    db.commit()
    db.refresh(agendamento)
    return agendamento


@router.get("/agendamentos", response_model=list[AgendamentoOut], responses=ERROS)
def listar_agenda(
    profissional: int = Query(..., description="id do profissional"),
    data: date = Query(..., description="dia no formato AAAA-MM-DD"),
    db: Session = Depends(get_db),
):
    _buscar(db, Profissional, profissional, "Profissional")
    return _agenda_do_dia(db, data, profissional_id=profissional)


# Precisa vir antes de /agendamentos/{agendamento_id} para não ser capturada por ela.
@router.get("/agendamentos/proximos", response_model=list[AgendamentoDetalhadoOut])
def proximos_agendamentos(db: Session = Depends(get_db)):
    """Agendamentos ativos de agora em diante, com nomes de cliente, profissional e serviço."""
    stmt = (
        select(Agendamento)
        .where(Agendamento.status == Status.ATIVO.value, Agendamento.inicio >= agora())
        .order_by(Agendamento.inicio)
    )
    return [
        AgendamentoDetalhadoOut(
            **AgendamentoOut.model_validate(a).model_dump(),
            cliente_nome=a.cliente.nome,
            profissional_nome=a.profissional.nome,
            servico_nome=a.servico.nome,
        )
        for a in db.scalars(stmt)
    ]


@router.get("/agendamentos/{agendamento_id}", response_model=AgendamentoOut, responses=ERROS)
def obter_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    return _buscar(db, Agendamento, agendamento_id, "Agendamento")


@router.patch("/agendamentos/{agendamento_id}/cancelar", response_model=AgendamentoOut, responses=ERROS)
def cancelar_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    agendamento = _buscar(db, Agendamento, agendamento_id, "Agendamento")
    regras.pode_cancelar(Status(agendamento.status), agendamento.inicio, agora())
    agendamento.status = Status.CANCELADO.value
    db.commit()
    return agendamento


@router.patch("/agendamentos/{agendamento_id}/concluir", response_model=AgendamentoOut, responses=ERROS)
def concluir_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    agendamento = _buscar(db, Agendamento, agendamento_id, "Agendamento")
    regras.validar_transicao(Status(agendamento.status), Status.CONCLUIDO)
    agendamento.status = Status.CONCLUIDO.value
    db.commit()
    return agendamento


# ------------------------------------------------------------------ disponibilidade
@router.get("/disponibilidade", response_model=DisponibilidadeOut, responses=ERROS)
def disponibilidade(
    profissional: int = Query(..., description="id do profissional"),
    servico: int = Query(..., description="id do serviço"),
    data: date = Query(..., description="dia no formato AAAA-MM-DD"),
    db: Session = Depends(get_db),
):
    prof = _buscar(db, Profissional, profissional, "Profissional")
    serv = _buscar(db, Servico, servico, "Serviço")
    dados_prof = prof.dados_regras()
    regras.validar_habilitacao(serv.id, dados_prof.servicos_habilitados)

    livres = regras.horarios_disponiveis(
        dia=data,
        duracao_min=serv.duracao_min,
        profissional=dados_prof,
        agenda_profissional=[a.periodo() for a in _agenda_do_dia(db, data, profissional_id=prof.id)],
        agora=agora(),
    )
    return DisponibilidadeOut(
        profissional_id=prof.id,
        servico_id=serv.id,
        data=data,
        horarios=[h.strftime("%H:%M") for h in livres],
    )
