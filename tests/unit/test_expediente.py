"""RN01, RN02, RN03 e RN11 — cálculo do fim, expediente, dias de trabalho e grade."""

from datetime import datetime, time

import pytest

from app.regras import (
    RegraNegocioError,
    calcular_fim,
    validar_dia_trabalho,
    validar_expediente,
    validar_grade_horario,
)

ABRE, FECHA = time(8, 0), time(18, 0)
SEG_A_SAB = {0, 1, 2, 3, 4, 5}
DURACAO = 30


def dia(hora: int, minuto: int = 0, d: int = 16) -> datetime:
    """Horário em novembro/2026 (16 = segunda-feira)."""
    return datetime(2026, 11, d, hora, minuto)


# ------------------------------------------------------------------ RN01
def test_ct01_fim_e_inicio_mais_duracao():
    """CT01 — partição: início 09:00 + 30 min = 09:30."""
    assert calcular_fim(dia(9), 30) == dia(9, 30)


def test_rn01_fim_pode_virar_a_hora():
    assert calcular_fim(dia(9, 45), 90) == dia(11, 15)


@pytest.mark.parametrize("duracao", [0, -15])
def test_rn01_duracao_invalida(duracao):
    with pytest.raises(ValueError):
        calcular_fim(dia(9), duracao)


# ------------------------------------------------------------------ RN02
@pytest.mark.parametrize(
    "inicio, aceito",
    [
        pytest.param(dia(8, 0), True, id="08:00 abertura exata"),
        pytest.param(dia(7, 59), False, id="07:59 um minuto antes"),
        pytest.param(dia(7, 45), False, id="CT04 07:45"),
        pytest.param(dia(12, 0), True, id="12:00 meio do expediente"),
        pytest.param(dia(17, 29), True, id="17:29 termina 17:59"),
        pytest.param(dia(17, 30), True, id="CT02 17:30 termina 18:00"),
        pytest.param(dia(17, 31), False, id="17:31 termina 18:01"),
        pytest.param(dia(17, 45), False, id="CT03 17:45 termina 18:15"),
    ],
)
def test_rn02_valor_limite_expediente(inicio, aceito):
    """Valor-limite nas duas bordas do expediente 08:00–18:00 (serviço de 30 min)."""
    fim = calcular_fim(inicio, DURACAO)
    if aceito:
        validar_expediente(inicio, fim, ABRE, FECHA)
    else:
        with pytest.raises(RegraNegocioError) as erro:
            validar_expediente(inicio, fim, ABRE, FECHA)
        assert erro.value.regra == "RN02"


def test_rn02_servico_que_atravessa_a_meia_noite_e_recusado():
    inicio = dia(23, 30)
    with pytest.raises(RegraNegocioError):
        validar_expediente(inicio, calcular_fim(inicio, 60), time(0, 0), time(23, 59))


# ------------------------------------------------------------------ RN03
def test_ct05_domingo_e_recusado():
    """CT05 — domingo 22/11/2026 às 10:00, profissional atende seg–sáb."""
    with pytest.raises(RegraNegocioError) as erro:
        validar_dia_trabalho(dia(10, d=22), SEG_A_SAB)
    assert erro.value.regra == "RN03"
    assert "domingo" in erro.value.mensagem


@pytest.mark.parametrize("d", [16, 17, 18, 19, 20, 21], ids=["seg", "ter", "qua", "qui", "sex", "sab"])
def test_rn03_dias_de_trabalho_sao_aceitos(d):
    validar_dia_trabalho(dia(10, d=d), SEG_A_SAB)


# ------------------------------------------------------------------ RN11
@pytest.mark.parametrize("minuto", [0, 15, 30, 45])
def test_rn11_multiplos_de_15_sao_aceitos(minuto):
    validar_grade_horario(dia(9, minuto))


@pytest.mark.parametrize("minuto", [1, 10, 14, 16, 59], ids=lambda m: f"09:{m:02d}")
def test_ct18_horario_fora_da_grade_e_recusado(minuto):
    """CT18 — 09:10 (e vizinhos das bordas 09:15) são recusados."""
    with pytest.raises(RegraNegocioError) as erro:
        validar_grade_horario(dia(9, minuto))
    assert erro.value.regra == "RN11"


def test_rn11_segundos_tambem_sao_recusados():
    with pytest.raises(RegraNegocioError):
        validar_grade_horario(datetime(2026, 11, 16, 9, 0, 30))
