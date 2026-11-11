"""Validação completa de um novo agendamento e cálculo da disponibilidade.

Aqui as regras são combinadas: interessa saber qual RN é reportada quando
mais de uma é violada ao mesmo tempo, e se a lista de horários livres só
oferece horários que seriam de fato aceitos.
"""

from datetime import date, datetime, time

import pytest

from app.regras import (
    DadosProfissional,
    Periodo,
    RegraNegocioError,
    Status,
    horarios_disponiveis,
    validar_novo_agendamento,
)

AGORA = datetime(2026, 11, 16, 8, 0)
CORTE, BARBA = 1, 2
ANA = DadosProfissional(
    abertura=time(8, 0),
    fechamento=time(18, 0),
    dias_trabalho=frozenset({0, 1, 2, 3, 4, 5}),
    servicos_habilitados=frozenset({CORTE}),
)


def validar(inicio, servico=CORTE, agenda_prof=(), agenda_cli=()):
    return validar_novo_agendamento(
        inicio=inicio,
        servico_id=servico,
        duracao_min=30,
        profissional=ANA,
        agenda_profissional=agenda_prof,
        agenda_cliente=agenda_cli,
        agora=AGORA,
    )


def test_agendamento_valido_devolve_o_fim():
    assert validar(datetime(2026, 11, 17, 10, 0)) == datetime(2026, 11, 17, 10, 30)


@pytest.mark.parametrize(
    "inicio, servico, agenda_prof, agenda_cli, regra",
    [
        pytest.param(datetime(2026, 11, 17, 10, 10), CORTE, (), (), "RN11", id="fora da grade"),
        pytest.param(datetime(2026, 11, 15, 10, 0), CORTE, (), (), "RN06",
                     id="CT10 ontem (também domingo) -> reporta passado"),
        pytest.param(datetime(2026, 11, 16, 8, 30), CORTE, (), (), "RN07", id="só 30 min de antecedência"),
        pytest.param(datetime(2026, 11, 17, 10, 0), BARBA, (), (), "RN09", id="não habilitado"),
        pytest.param(datetime(2026, 11, 22, 10, 0), CORTE, (), (), "RN03", id="domingo"),
        pytest.param(datetime(2026, 11, 17, 17, 45), CORTE, (), (), "RN02", id="fora do expediente"),
        pytest.param(datetime(2026, 11, 17, 10, 0), CORTE,
                     [Periodo(datetime(2026, 11, 17, 10, 0), datetime(2026, 11, 17, 10, 30))], (),
                     "RN04", id="profissional ocupado"),
        pytest.param(datetime(2026, 11, 17, 10, 0), CORTE, (),
                     [Periodo(datetime(2026, 11, 17, 10, 0), datetime(2026, 11, 17, 10, 30))],
                     "RN10", id="cliente ocupado"),
    ],
)
def test_cada_regra_violada_e_reportada(inicio, servico, agenda_prof, agenda_cli, regra):
    with pytest.raises(RegraNegocioError) as erro:
        validar(inicio, servico, agenda_prof, agenda_cli)
    assert erro.value.regra == regra


# ------------------------------------------------------------------ disponibilidade
def livres(dia, agenda=(), duracao=30, prof=ANA):
    return [
        h.strftime("%H:%M")
        for h in horarios_disponiveis(
            dia=dia, duracao_min=duracao, profissional=prof, agenda_profissional=agenda, agora=AGORA
        )
    ]


def test_dia_livre_tem_todos_os_horarios_da_grade():
    horarios = livres(date(2026, 11, 17))
    assert horarios[0] == "08:00"
    assert horarios[-1] == "17:30"  # último que termina até 18:00
    assert len(horarios) == 39       # 08:00..17:30 de 15 em 15


def test_hoje_respeita_antecedencia_minima():
    assert livres(date(2026, 11, 16))[0] == "09:00"


def test_domingo_nao_tem_horarios():
    assert livres(date(2026, 11, 22)) == []


def test_horario_ocupado_e_vizinhos_que_conflitam_somem():
    ocupado = Periodo(datetime(2026, 11, 17, 10, 0), datetime(2026, 11, 17, 10, 30))
    horarios = livres(date(2026, 11, 17), [ocupado])
    assert {"09:45", "10:00", "10:15"}.isdisjoint(horarios)
    assert {"09:30", "10:30"} <= set(horarios)  # RN05: encostar é permitido


def test_agendamento_cancelado_nao_bloqueia_disponibilidade():
    cancelado = Periodo(datetime(2026, 11, 17, 10, 0), datetime(2026, 11, 17, 10, 30), Status.CANCELADO)
    assert "10:00" in livres(date(2026, 11, 17), [cancelado])


def test_servico_longo_reduz_ultimo_horario():
    assert livres(date(2026, 11, 17), duracao=90)[-1] == "16:30"


def test_expediente_quebrado_e_alinhado_a_grade():
    prof = DadosProfissional(time(8, 10), time(10, 0), frozenset({1}), frozenset({CORTE}))
    assert livres(date(2026, 11, 17), prof=prof)[0] == "08:15"
