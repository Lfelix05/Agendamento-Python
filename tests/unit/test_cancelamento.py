"""RN08 (tabela de decisão) e transições de estado do agendamento."""

from datetime import datetime, timedelta

import pytest

from app.regras import (
    EstadoInvalidoError,
    RegraNegocioError,
    Status,
    pode_cancelar,
    validar_transicao,
)

AGORA = datetime(2026, 11, 16, 8, 0)
FALTAM_24H = AGORA + timedelta(hours=24)
FALTAM_23H59 = AGORA + timedelta(hours=23, minutes=59)


# Tabela de decisão do cancelamento
# | Regra | Status    | Antecedência >= 24h | Resultado              |
# |-------|-----------|---------------------|------------------------|
# | R1    | ativo     | sim                 | cancela                |
# | R2    | ativo     | não                 | recusa (RN08)          |
# | R3    | cancelado | sim / não           | recusa (estado)        |
# | R4    | concluido | sim / não           | recusa (estado)        |
@pytest.mark.parametrize(
    "status, inicio, esperado",
    [
        pytest.param(Status.ATIVO, FALTAM_24H, None, id="R1 CT13 ativo, 24h exatas"),
        pytest.param(Status.ATIVO, AGORA + timedelta(days=2), None, id="R1 ativo, 2 dias"),
        pytest.param(Status.ATIVO, FALTAM_23H59, "RN08", id="R2 CT14 ativo, 23h59"),
        pytest.param(Status.ATIVO, AGORA + timedelta(hours=2), "RN08", id="R2 ativo, 2h"),
        pytest.param(Status.CANCELADO, FALTAM_24H, "ESTADO", id="R3 CT15 já cancelado, 24h"),
        pytest.param(Status.CANCELADO, FALTAM_23H59, "ESTADO", id="R3 já cancelado, 23h59"),
        pytest.param(Status.CONCLUIDO, FALTAM_24H, "ESTADO", id="R4 concluído, 24h"),
        pytest.param(Status.CONCLUIDO, FALTAM_23H59, "ESTADO", id="R4 concluído, 23h59"),
    ],
)
def test_rn08_tabela_de_decisao_cancelamento(status, inicio, esperado):
    if esperado is None:
        pode_cancelar(status, inicio, AGORA)
    else:
        with pytest.raises(RegraNegocioError) as erro:
            pode_cancelar(status, inicio, AGORA)
        assert erro.value.regra == esperado


def test_ct15_cancelar_ja_cancelado_e_estado_invalido():
    with pytest.raises(EstadoInvalidoError):
        pode_cancelar(Status.CANCELADO, FALTAM_24H, AGORA)


# Transição de estado: ativo -> cancelado | concluido; estados finais não mudam.
@pytest.mark.parametrize(
    "atual, novo, permitido",
    [
        (Status.ATIVO, Status.CANCELADO, True),
        (Status.ATIVO, Status.CONCLUIDO, True),
        (Status.ATIVO, Status.ATIVO, False),
        (Status.CANCELADO, Status.ATIVO, False),
        (Status.CANCELADO, Status.CONCLUIDO, False),
        (Status.CANCELADO, Status.CANCELADO, False),
        (Status.CONCLUIDO, Status.ATIVO, False),
        (Status.CONCLUIDO, Status.CANCELADO, False),
        (Status.CONCLUIDO, Status.CONCLUIDO, False),
    ],
    ids=lambda v: v.value if isinstance(v, Status) else ("ok" if v else "erro"),
)
def test_transicoes_de_estado(atual, novo, permitido):
    if permitido:
        validar_transicao(atual, novo)
    else:
        with pytest.raises(EstadoInvalidoError):
            validar_transicao(atual, novo)
