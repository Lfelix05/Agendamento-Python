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


class ClienteCreate(BaseModel):
    nome: str
    telefone: str

    @field_validator("nome")
    @classmethod
    def nome_valido(cls, valor: str) -> str:
        valor = " ".join(valor.split())
        if len(valor) < 2:
            raise ValueError("informe o nome do cliente")
        return valor

    @field_validator("telefone")
    @classmethod
    def telefone_valido(cls, valor: str) -> str:
        """Aceita qualquer formatação e guarda no padrão (DD) 99999-9999."""
        digitos = "".join(c for c in valor if c.isdigit())
        if len(digitos) == 11:
            return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
        if len(digitos) == 10:
            return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
        raise ValueError("telefone deve ter DDD + número (10 ou 11 dígitos)")


class AgendamentoDetalhadoOut(AgendamentoOut):
    """Agendamento com os nomes, para exibir na lateral da página."""

    cliente_nome: str
    profissional_nome: str
    servico_nome: str


class DisponibilidadeOut(BaseModel):
    profissional_id: int
    servico_id: int
    data: date
    horarios: list[str]  # "HH:MM"


class ErroOut(BaseModel):
    detail: str
    regra: str | None = None
