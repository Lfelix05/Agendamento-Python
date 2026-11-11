"""RN09 — o profissional precisa estar habilitado para o serviço."""

import pytest

from app.regras import RegraNegocioError, validar_habilitacao

CORTE, BARBA, COLORACAO = 1, 2, 3
HABILITADOS_ANA = {CORTE, COLORACAO}


@pytest.mark.parametrize("servico", [CORTE, COLORACAO])
def test_rn09_servico_habilitado_e_aceito(servico):
    validar_habilitacao(servico, HABILITADOS_ANA)


def test_ct16_servico_nao_habilitado_e_recusado():
    """CT16 — Ana não faz barba."""
    with pytest.raises(RegraNegocioError) as erro:
        validar_habilitacao(BARBA, HABILITADOS_ANA)
    assert erro.value.regra == "RN09"


def test_rn09_profissional_sem_servicos_recusa_tudo():
    with pytest.raises(RegraNegocioError):
        validar_habilitacao(CORTE, set())
