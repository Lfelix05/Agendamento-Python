"""Modelos Pydantic de entrada e saída da API."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, field_validator


class AgendamentoCreate(BaseModel):
    cliente_id: int
    profissional_id: int
    servico_id: int
    inicio: datetime

    @field_validator("inicio")
    @classmethod
    def sem_fuso(cls, valor: datetime) -> datetime:
        # Decisão de projeto: todo o sistema trabalha em horário local, sem fuso.
        if valor.tzinfo is not None:
            raise ValueError("informe o horário local, sem fuso (ex.: 2026-11-17T10:00)")
        return valor


class AgendamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    profissional_id: int
    servico_id: int
    inicio: datetime
    fim: datetime
    status: str


class ServicoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    duracao_min: int
    preco: float


class ProfissionalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    inicio_expediente: time
    fim_expediente: time
    dias_trabalho: str
    servicos: list[ServicoOut]


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    telefone: str


class DisponibilidadeOut(BaseModel):
    profissional_id: int
    servico_id: int
    data: date
    horarios: list[str]  # "HH:MM"


class ErroOut(BaseModel):
    detail: str
    regra: str | None = None
