"""Regras de negócio RN01–RN11 como funções puras.

Nenhuma função deste módulo acessa banco de dados, HTTP ou o relógio do
sistema: o "agora" sempre chega por parâmetro. Isso permite testar cada regra
isoladamente, em milissegundos e de forma determinística.

Decisão de projeto: todos os horários são ``datetime`` sem fuso (horário local).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum

ANTECEDENCIA_MINIMA = timedelta(hours=1)          # RN07
ANTECEDENCIA_CANCELAMENTO = timedelta(hours=24)   # RN08
GRADE_MINUTOS = 15                                # RN11


class Status(str, Enum):
    ATIVO = "ativo"
    CANCELADO = "cancelado"
    CONCLUIDO = "concluido"


# Transições de estado permitidas: ativo -> cancelado | concluido.
# Estados finais (cancelado, concluido) não saem para lugar nenhum.
TRANSICOES: dict[Status, set[Status]] = {
    Status.ATIVO: {Status.CANCELADO, Status.CONCLUIDO},
    Status.CANCELADO: set(),
    Status.CONCLUIDO: set(),
}


class RegraNegocioError(Exception):
    """Violação de uma regra de negócio. ``regra`` identifica a RN (ex.: "RN02")."""

    def __init__(self, regra: str, mensagem: str):
        super().__init__(mensagem)
        self.regra = regra
        self.mensagem = mensagem


class ConflitoError(RegraNegocioError):
    """Conflito de horário (RN04 / RN10)."""


class EstadoInvalidoError(RegraNegocioError):
    """Transição de estado não permitida."""


@dataclass(frozen=True)
class Periodo:
    """Um intervalo ocupado na agenda. ``fim`` é exclusivo: [inicio, fim)."""

    inicio: datetime
    fim: datetime
    status: Status = Status.ATIVO


# ---------------------------------------------------------------- RN01
def calcular_fim(inicio: datetime, duracao_min: int) -> datetime:
    """RN01: fim = início + duração do serviço."""
    if duracao_min <= 0:
        raise ValueError("A duração do serviço deve ser positiva.")
    return inicio + timedelta(minutes=duracao_min)


# ---------------------------------------------------------------- RN02
def validar_expediente(inicio: datetime, fim: datetime, abertura: time, fechamento: time) -> None:
    """RN02: o atendimento deve começar e terminar dentro do expediente."""
    abre = datetime.combine(inicio.date(), abertura)
    fecha = datetime.combine(inicio.date(), fechamento)
    if inicio < abre or fim > fecha:
        raise RegraNegocioError(
            "RN02",
            f"Horário fora do expediente do profissional "
            f"({abertura:%H:%M}–{fechamento:%H:%M}).",
        )


# ---------------------------------------------------------------- RN03
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def validar_dia_trabalho(inicio: datetime, dias_trabalho: Iterable[int]) -> None:
    """RN03: ``dias_trabalho`` usa a convenção de ``weekday()`` (0 = segunda)."""
    if inicio.weekday() not in set(dias_trabalho):
        raise RegraNegocioError(
            "RN03", f"O profissional não atende neste dia ({DIAS_SEMANA[inicio.weekday()]})."
        )


# ---------------------------------------------------------- RN04 / RN05
def ha_sobreposicao(inicio_a: datetime, fim_a: datetime, inicio_b: datetime, fim_b: datetime) -> bool:
    """Intervalos semiabertos [inicio, fim): encostar não é sobrepor (RN05)."""
    return inicio_a < fim_b and inicio_b < fim_a


def ha_conflito(inicio: datetime, fim: datetime, existentes: Iterable[Periodo]) -> bool:
    """RN04/RN05: só agendamentos ATIVOS ocupam a agenda."""
    return any(
        p.status == Status.ATIVO and ha_sobreposicao(inicio, fim, p.inicio, p.fim)
        for p in existentes
    )


def validar_conflito_profissional(inicio: datetime, fim: datetime, agenda: Iterable[Periodo]) -> None:
    """RN04: o profissional não pode ter dois atendimentos ativos sobrepostos."""
    if ha_conflito(inicio, fim, agenda):
        raise ConflitoError("RN04", "O profissional já possui um agendamento neste horário.")


# ---------------------------------------------------------------- RN06 / RN07
def validar_antecedencia(inicio: datetime, agora: datetime) -> None:
    """RN06: não agendar no passado. RN07: antecedência mínima de 1 hora."""
    if inicio < agora:
        raise RegraNegocioError("RN06", "Não é possível agendar em uma data no passado.")
    if inicio - agora < ANTECEDENCIA_MINIMA:
        raise RegraNegocioError("RN07", "É necessária antecedência mínima de 1 hora para agendar.")


# ---------------------------------------------------------------- RN08 + estados
def validar_transicao(atual: Status, novo: Status) -> None:
    """Teste de transição de estado: só ativo -> cancelado | concluido."""
    if Status(novo) not in TRANSICOES[Status(atual)]:
        raise EstadoInvalidoError(
            "ESTADO", f"Não é possível mudar um agendamento de '{Status(atual).value}' "
            f"para '{Status(novo).value}'."
        )


def pode_cancelar(status: Status, inicio: datetime, agora: datetime) -> None:
    """RN08: cancelamento só de agendamento ativo e com pelo menos 24h de antecedência."""
    validar_transicao(status, Status.CANCELADO)
    if inicio - agora < ANTECEDENCIA_CANCELAMENTO:
        raise RegraNegocioError(
            "RN08", "O cancelamento exige pelo menos 24 horas de antecedência."
        )


# ---------------------------------------------------------------- RN09
def validar_habilitacao(servico_id: int, servicos_habilitados: Iterable[int]) -> None:
    """RN09: o profissional precisa estar habilitado para o serviço."""
    if servico_id not in set(servicos_habilitados):
        raise RegraNegocioError("RN09", "O profissional não está habilitado para este serviço.")


# ---------------------------------------------------------------- RN10
def validar_conflito_cliente(inicio: datetime, fim: datetime, agenda_cliente: Iterable[Periodo]) -> None:
    """RN10: o cliente não pode estar em dois atendimentos ativos ao mesmo tempo."""
    if ha_conflito(inicio, fim, agenda_cliente):
        raise ConflitoError("RN10", "O cliente já possui um agendamento neste horário.")


# ---------------------------------------------------------------- RN11
def validar_grade_horario(inicio: datetime) -> None:
    """RN11: início só em múltiplos de 15 minutos (sem segundos)."""
    if inicio.minute % GRADE_MINUTOS or inicio.second or inicio.microsecond:
        raise RegraNegocioError(
            "RN11", "O horário de início deve ser múltiplo de 15 minutos (ex.: 09:00, 09:15)."
        )


# ---------------------------------------------------------------- validação completa
@dataclass(frozen=True)
class DadosProfissional:
    abertura: time
    fechamento: time
    dias_trabalho: frozenset[int]
    servicos_habilitados: frozenset[int]


def validar_novo_agendamento(
    *,
    inicio: datetime,
    servico_id: int,
    duracao_min: int,
    profissional: DadosProfissional,
    agenda_profissional: Iterable[Periodo],
    agenda_cliente: Iterable[Periodo],
    agora: datetime,
) -> datetime:
    """Aplica todas as regras na ordem abaixo e devolve o horário de fim (RN01).

    A ordem importa para a mensagem de erro: entradas malformadas (RN11) e
    tempo (RN06/RN07) primeiro, depois cadastro (RN09), agenda (RN03/RN02) e,
    por último, conflitos (RN04/RN10), que são os únicos que exigem consulta.
    """
    validar_grade_horario(inicio)
    validar_antecedencia(inicio, agora)
    validar_habilitacao(servico_id, profissional.servicos_habilitados)
    fim = calcular_fim(inicio, duracao_min)
    validar_dia_trabalho(inicio, profissional.dias_trabalho)
    validar_expediente(inicio, fim, profissional.abertura, profissional.fechamento)
    validar_conflito_profissional(inicio, fim, agenda_profissional)
    validar_conflito_cliente(inicio, fim, agenda_cliente)
    return fim


# ---------------------------------------------------------------- disponibilidade
def horarios_disponiveis(
    *,
    dia: date,
    duracao_min: int,
    profissional: DadosProfissional,
    agenda_profissional: Iterable[Periodo],
    agora: datetime,
) -> list[datetime]:
    """Horários de início livres no dia, na grade de 15 minutos.

    Reaproveita as mesmas regras do agendamento (RN02, RN03, RN04, RN06, RN07),
    garantindo que todo horário listado seria de fato aceito.
    """
    agenda = list(agenda_profissional)
    passo = timedelta(minutes=GRADE_MINUTOS)
    candidato = datetime.combine(dia, profissional.abertura)
    # alinha à grade caso o expediente comece "quebrado" (ex.: 08:10 -> 08:15)
    resto = candidato.minute % GRADE_MINUTOS
    if resto:
        candidato += timedelta(minutes=GRADE_MINUTOS - resto)
    fechamento = datetime.combine(dia, profissional.fechamento)

    livres: list[datetime] = []
    while candidato < fechamento:
        fim = calcular_fim(candidato, duracao_min)
        try:
            validar_antecedencia(candidato, agora)
            validar_dia_trabalho(candidato, profissional.dias_trabalho)
            validar_expediente(candidato, fim, profissional.abertura, profissional.fechamento)
            validar_conflito_profissional(candidato, fim, agenda)
        except RegraNegocioError:
            pass
        else:
            livres.append(candidato)
        candidato += passo
    return livres
