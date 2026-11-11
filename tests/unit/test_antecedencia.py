"""RN06 e RN07 — não agendar no passado e antecedência mínima de 1 hora.

O "agora" é passado como parâmetro, então o teste não depende do relógio real:
é sempre segunda-feira, 16/11/2026, 08:00.
"""

from datetime import datetime

import pytest

from app.regras import RegraNegocioError, validar_antecedencia

AGORA = datetime(2026, 11, 16, 8, 0)


def test_ct10_ontem_e_recusado():
    """CT10 — ontem às 10:00 está no passado."""
    with pytest.raises(RegraNegocioError) as erro:
        validar_antecedencia(datetime(2026, 11, 15, 10, 0), AGORA)
    assert erro.value.regra == "RN06"


def test_rn06_um_minuto_atras_e_passado():
    with pytest.raises(RegraNegocioError) as erro:
        validar_antecedencia(datetime(2026, 11, 16, 7, 59), AGORA)
    assert erro.value.regra == "RN06"


@pytest.mark.parametrize(
    "inicio, aceito",
    [
        pytest.param(datetime(2026, 11, 16, 8, 0), False, id="agora mesmo (0 min)"),
        pytest.param(datetime(2026, 11, 16, 8, 45), False, id="CT12 08:45 (45 min)"),
        pytest.param(datetime(2026, 11, 16, 8, 59), False, id="08:59 (59 min)"),
        pytest.param(datetime(2026, 11, 16, 9, 0), True, id="CT11 09:00 (exatamente 1h)"),
        pytest.param(datetime(2026, 11, 16, 9, 1), True, id="09:01 (61 min)"),
        pytest.param(datetime(2026, 11, 17, 8, 0), True, id="amanhã"),
    ],
)
def test_rn07_valor_limite_antecedencia_minima(inicio, aceito):
    if aceito:
        validar_antecedencia(inicio, AGORA)
    else:
        with pytest.raises(RegraNegocioError) as erro:
            validar_antecedencia(inicio, AGORA)
        assert erro.value.regra == "RN07"
