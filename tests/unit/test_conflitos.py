"""RN04, RN05 e RN10 — conflitos de horário do profissional e do cliente."""

from datetime import datetime

import pytest

from app.regras import (
    ConflitoError,
    Periodo,
    Status,
    calcular_fim,
    ha_conflito,
    ha_sobreposicao,
    validar_conflito_cliente,
    validar_conflito_profissional,
)


def h(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, 16, hora, minuto)


EXISTENTE = Periodo(h(10), h(10, 30))  # agendamento ativo 10:00–10:30


@pytest.mark.parametrize(
    "inicio, conflita",
    [
        pytest.param(h(9, 30), False, id="CT09 09:30-10:00 encosta antes"),
        pytest.param(h(9, 45), True, id="09:45-10:15 invade o início"),
        pytest.param(h(10, 0), True, id="10:00-10:30 mesmo horário"),
        pytest.param(h(10, 15), True, id="CT06 10:15-10:45 invade o fim"),
        pytest.param(h(10, 30), False, id="CT08 10:30-11:00 encosta depois"),
        pytest.param(h(11, 0), False, id="11:00-11:30 longe"),
    ],
)
def test_rn04_rn05_conflito_com_agendamento_existente(inicio, conflita):
    """Valor-limite em torno do intervalo 10:00–10:30 (serviço de 30 min)."""
    fim = calcular_fim(inicio, 30)
    assert ha_conflito(inicio, fim, [EXISTENTE]) is conflita


def test_ct06_profissional_ocupado_lanca_conflito():
    with pytest.raises(ConflitoError) as erro:
        validar_conflito_profissional(h(10, 15), h(10, 45), [EXISTENTE])
    assert erro.value.regra == "RN04"


@pytest.mark.parametrize("status", [Status.CANCELADO, Status.CONCLUIDO])
def test_ct07_agendamento_nao_ativo_nao_ocupa_horario(status):
    """CT07 — um agendamento cancelado (ou concluído) libera o horário."""
    liberado = Periodo(h(10), h(10, 30), status)
    validar_conflito_profissional(h(10), h(10, 30), [liberado])


def test_rn04_novo_agendamento_que_engloba_o_existente():
    """Serviço longo (90 min) que cobre totalmente um agendamento curto."""
    assert ha_conflito(h(9, 30), h(11), [EXISTENTE])


def test_rn04_agenda_vazia_nunca_conflita():
    assert not ha_conflito(h(10), h(10, 30), [])


def test_sobreposicao_e_simetrica():
    a = (h(10), h(10, 30))
    b = (h(10, 15), h(10, 45))
    assert ha_sobreposicao(*a, *b) == ha_sobreposicao(*b, *a) is True


def test_ct17_cliente_ja_ocupado_com_outro_profissional():
    """CT17 — RN10: o cliente já tem 10:00 com outro profissional."""
    agenda_cliente = [Periodo(h(10), h(10, 30))]
    with pytest.raises(ConflitoError) as erro:
        validar_conflito_cliente(h(10), h(10, 30), agenda_cliente)
    assert erro.value.regra == "RN10"


def test_rn10_cliente_pode_encadear_atendimentos():
    """RN05 também vale para o cliente: corte 10:00–10:30 e barba às 10:30."""
    validar_conflito_cliente(h(10, 30), h(11), [Periodo(h(10), h(10, 30))])
