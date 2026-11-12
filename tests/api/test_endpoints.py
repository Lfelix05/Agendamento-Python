"""Testes de API (CT19–CT23 e complementares).

Chamam os endpoints de verdade via TestClient, com banco em memória e relógio
congelado em segunda-feira, 16/11/2026, 08:00 (fixture ``relogio``).
"""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import Agendamento, Cliente

pytestmark = pytest.mark.usefixtures("relogio")

TERCA_10H = "2026-11-17T10:00:00"


def agendar(client, dados, inicio=TERCA_10H, cliente="joao", profissional="ana", servico="corte"):
    return client.post(
        "/agendamentos",
        json={
            "cliente_id": dados[cliente].id,
            "profissional_id": dados[profissional].id,
            "servico_id": dados[servico].id,
            "inicio": inicio,
        },
    )


# ------------------------------------------------------------------ CT19–CT23
def test_ct19_post_valido_cria_e_grava_no_banco(client, dados, db):
    resposta = agendar(client, dados)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["inicio"] == TERCA_10H
    assert corpo["fim"] == "2026-11-17T10:30:00"  # RN01
    assert corpo["status"] == "ativo"

    gravado = db.scalar(select(Agendamento).where(Agendamento.id == corpo["id"]))
    assert gravado is not None
    assert gravado.profissional_id == dados["ana"].id


def test_ct20_post_em_horario_ocupado_retorna_409(client, dados):
    assert agendar(client, dados, cliente="joao").status_code == 201

    resposta = agendar(client, dados, inicio="2026-11-17T10:15:00", cliente="maria")

    assert resposta.status_code == 409
    assert resposta.json() == {
        "detail": "O profissional já possui um agendamento neste horário.",
        "regra": "RN04",
    }


@pytest.mark.parametrize("campo", ["cliente_id", "profissional_id", "servico_id", "inicio"])
def test_ct21_post_sem_campo_obrigatorio_retorna_422(client, dados, campo):
    corpo = {
        "cliente_id": dados["joao"].id,
        "profissional_id": dados["ana"].id,
        "servico_id": dados["corte"].id,
        "inicio": TERCA_10H,
    }
    del corpo[campo]
    resposta = client.post("/agendamentos", json=corpo)
    assert resposta.status_code == 422
    assert resposta.json()["detail"][0]["loc"] == ["body", campo]


def test_ct22_horario_ocupado_some_da_disponibilidade(client, dados):
    params = {"profissional": dados["ana"].id, "servico": dados["corte"].id, "data": "2026-11-17"}
    antes = client.get("/disponibilidade", params=params).json()["horarios"]
    assert "10:00" in antes

    agendar(client, dados)

    depois = client.get("/disponibilidade", params=params).json()["horarios"]
    assert "10:00" not in depois
    assert "10:15" not in depois
    assert "10:30" in depois  # RN05
    assert len(depois) == len(antes) - 3  # 09:45, 10:00 e 10:15


def test_ct23_cancelar_com_dois_dias_de_antecedencia(client, dados, db):
    id_ = agendar(client, dados, inicio="2026-11-18T10:00:00").json()["id"]

    resposta = client.patch(f"/agendamentos/{id_}/cancelar")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "cancelado"
    assert db.get(Agendamento, id_).status == "cancelado"


# ------------------------------------------------------------------ complementares
def test_cancelar_com_menos_de_24h_retorna_400(client, dados):
    id_ = agendar(client, dados, inicio="2026-11-16T15:00:00").json()["id"]
    resposta = client.patch(f"/agendamentos/{id_}/cancelar")
    assert resposta.status_code == 400
    assert resposta.json()["regra"] == "RN08"


def test_cancelar_duas_vezes_retorna_409(client, dados):
    id_ = agendar(client, dados, inicio="2026-11-18T10:00:00").json()["id"]
    assert client.patch(f"/agendamentos/{id_}/cancelar").status_code == 200
    assert client.patch(f"/agendamentos/{id_}/cancelar").status_code == 409


def test_horario_cancelado_volta_a_ficar_livre(client, dados):
    id_ = agendar(client, dados, inicio="2026-11-18T10:00:00").json()["id"]
    client.patch(f"/agendamentos/{id_}/cancelar")
    assert agendar(client, dados, inicio="2026-11-18T10:00:00", cliente="maria").status_code == 201


def test_concluir_e_depois_cancelar_e_recusado(client, dados):
    id_ = agendar(client, dados).json()["id"]
    concluido = client.patch(f"/agendamentos/{id_}/concluir")
    assert concluido.status_code == 200
    assert concluido.json()["status"] == "concluido"
    assert client.patch(f"/agendamentos/{id_}/cancelar").status_code == 409


def test_rn10_cliente_ocupado_com_outro_profissional_retorna_409(client, dados):
    agendar(client, dados, profissional="ana")
    resposta = agendar(client, dados, profissional="bruno")
    assert resposta.status_code == 409
    assert resposta.json()["regra"] == "RN10"


@pytest.mark.parametrize(
    "inicio, servico, regra",
    [
        ("2026-11-15T10:00:00", "corte", "RN06"),
        ("2026-11-16T08:45:00", "corte", "RN07"),
        ("2026-11-17T10:00:00", "barba", "RN09"),
        ("2026-11-22T10:00:00", "corte", "RN03"),
        ("2026-11-17T17:45:00", "corte", "RN02"),
        ("2026-11-17T09:10:00", "corte", "RN11"),
    ],
)
def test_regras_violadas_retornam_400_com_a_rn(client, dados, inicio, servico, regra):
    resposta = agendar(client, dados, inicio=inicio, servico=servico)
    assert resposta.status_code == 400
    assert resposta.json()["regra"] == regra


def test_horario_com_fuso_e_recusado(client, dados):
    resposta = agendar(client, dados, inicio="2026-11-17T10:00:00-03:00")
    assert resposta.status_code == 422


@pytest.mark.parametrize("campo", ["cliente_id", "profissional_id", "servico_id"])
def test_registro_inexistente_retorna_404(client, dados, campo):
    corpo = {
        "cliente_id": dados["joao"].id,
        "profissional_id": dados["ana"].id,
        "servico_id": dados["corte"].id,
        "inicio": TERCA_10H,
    }
    corpo[campo] = 999
    assert client.post("/agendamentos", json=corpo).status_code == 404


def test_listar_agenda_do_dia_em_ordem(client, dados):
    agendar(client, dados, inicio="2026-11-17T14:00:00", cliente="joao")
    agendar(client, dados, inicio="2026-11-17T09:00:00", cliente="maria")
    agendar(client, dados, inicio="2026-11-18T09:00:00", cliente="pedro")  # outro dia

    resposta = client.get("/agendamentos", params={"profissional": dados["ana"].id, "data": "2026-11-17"})

    assert resposta.status_code == 200
    assert [a["inicio"][11:16] for a in resposta.json()] == ["09:00", "14:00"]


def test_obter_agendamento_por_id(client, dados):
    id_ = agendar(client, dados).json()["id"]
    assert client.get(f"/agendamentos/{id_}").json()["id"] == id_
    assert client.get("/agendamentos/999").status_code == 404


def test_disponibilidade_de_servico_nao_habilitado_retorna_400(client, dados):
    params = {"profissional": dados["ana"].id, "servico": dados["barba"].id, "data": "2026-11-17"}
    resposta = client.get("/disponibilidade", params=params)
    assert resposta.status_code == 400
    assert resposta.json()["regra"] == "RN09"


def test_cadastros_para_o_formulario(client, dados):
    assert len(client.get("/clientes").json()) == 3
    assert len(client.get("/servicos").json()) == 4
    profissionais = client.get("/profissionais").json()
    ana = next(p for p in profissionais if p["nome"] == "Ana Lima")
    assert {s["nome"] for s in ana["servicos"]} == {"Corte de cabelo", "Coloração"}


def test_pagina_inicial_e_servida(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert 'id="form-agendamento"' in resposta.text


def test_seed_nao_duplica_dados(db, dados):
    from app import seed

    assert seed.popular(db) is False


# ------------------------------------------------------------------ cadastro de clientes
@pytest.mark.parametrize(
    "telefone, gravado",
    [
        ("48988887777", "(48) 98888-7777"),
        ("(48) 98888-7777", "(48) 98888-7777"),
        ("48 3333-4444", "(48) 3333-4444"),
    ],
)
def test_post_cliente_cria_e_padroniza_telefone(client, db, telefone, gravado):
    resposta = client.post("/clientes", json={"nome": "  Lucas   Félix ", "telefone": telefone})

    assert resposta.status_code == 201
    assert resposta.json()["nome"] == "Lucas Félix"
    assert resposta.json()["telefone"] == gravado
    assert db.get(Cliente, resposta.json()["id"]) is not None


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param({"nome": "", "telefone": "48988887777"}, id="nome vazio"),
        pytest.param({"nome": "A", "telefone": "48988887777"}, id="nome com 1 letra"),
        pytest.param({"nome": "Lucas", "telefone": "988887777"}, id="telefone sem DDD"),
        pytest.param({"nome": "Lucas", "telefone": "489888877771"}, id="telefone com 12 dígitos"),
        pytest.param({"nome": "Lucas"}, id="sem telefone"),
    ],
)
def test_post_cliente_invalido_retorna_422(client, corpo):
    assert client.post("/clientes", json=corpo).status_code == 422


def test_post_cliente_com_telefone_repetido_retorna_409(client, dados):
    # João Pereira já usa (48) 99999-0001 no seed; formatação diferente, mesmo número
    resposta = client.post("/clientes", json={"nome": "Outro João", "telefone": "48 99999 0001"})
    assert resposta.status_code == 409


def test_cliente_novo_pode_agendar(client, dados):
    novo = client.post("/clientes", json={"nome": "Lucas", "telefone": "48988887777"}).json()
    resposta = client.post(
        "/agendamentos",
        json={"cliente_id": novo["id"], "profissional_id": dados["ana"].id,
              "servico_id": dados["corte"].id, "inicio": TERCA_10H},
    )
    assert resposta.status_code == 201


# ------------------------------------------------------------------ lateral: próximos agendamentos
def test_proximos_lista_so_ativos_futuros_em_ordem_com_nomes(client, dados, db):
    agendar(client, dados, inicio="2026-11-18T10:00:00", cliente="maria")
    agendar(client, dados, inicio="2026-11-17T10:00:00", cliente="joao")
    cancelado = agendar(client, dados, inicio="2026-11-19T10:00:00", cliente="pedro").json()["id"]
    client.patch(f"/agendamentos/{cancelado}/cancelar")
    # agendamento antigo (gravado direto no banco, pois a API não deixa criar no passado)
    db.add(Agendamento(cliente_id=dados["pedro"].id, profissional_id=dados["ana"].id,
                       servico_id=dados["corte"].id, inicio=datetime(2026, 11, 13, 10),
                       fim=datetime(2026, 11, 13, 10, 30), status="ativo"))
    db.commit()

    resposta = client.get("/agendamentos/proximos")

    assert resposta.status_code == 200
    itens = resposta.json()
    assert [(i["cliente_nome"], i["inicio"]) for i in itens] == [
        ("João Pereira", "2026-11-17T10:00:00"),
        ("Maria Souza", "2026-11-18T10:00:00"),
    ]
    assert itens[0]["profissional_nome"] == "Ana Lima"
    assert itens[0]["servico_nome"] == "Corte de cabelo"
