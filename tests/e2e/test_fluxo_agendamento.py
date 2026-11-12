"""CT24 e CT25 — o usuário agenda pelo navegador (Playwright).

Rodar com vídeo:  pytest tests/e2e --video=on
Rodar vendo o navegador:  pytest tests/e2e --headed --slowmo 500
Screenshots e vídeos ficam em test-results/.
"""

from datetime import date, timedelta

import httpx
from playwright.sync_api import Page, expect

PRINTS = "test-results"


def proximo_dia_util(a_partir_de: int = 2) -> date:
    """Primeiro dia de segunda a sexta, pelo menos ``a_partir_de`` dias à frente."""
    dia = date.today() + timedelta(days=a_partir_de)
    while dia.weekday() > 4:
        dia += timedelta(days=1)
    return dia


def preencher(page: Page, cliente: str, profissional: str, servico: str, dia: date, hora: str):
    page.select_option("#cliente", label=cliente)
    page.select_option("#profissional", label=profissional)
    page.select_option("#servico", label=servico)
    page.fill("#data", dia.isoformat())
    page.fill("#hora", hora)


def test_ct24_usuario_agenda_com_sucesso(page: Page):
    dia = proximo_dia_util()
    page.goto("/")
    expect(page.locator("h1")).to_have_text("Agendar serviço")

    preencher(page, "Maria Souza", "Bruno Costa", "Barba (30 min)", dia, "10:00")
    expect(page.locator("#horarios")).to_contain_text("10:00")
    page.click("#agendar")

    mensagem = page.locator("#mensagem")
    expect(mensagem).to_have_class("mensagem sucesso")
    expect(mensagem).to_have_text(f"Agendamento confirmado para {dia:%d/%m/%Y} às 10:00.")
    # o horário recém-ocupado some da lista de horários livres
    expect(page.locator("#horarios button", has_text="10:00")).to_have_count(0)
    page.screenshot(path=f"{PRINTS}/ct24_sucesso.png", full_page=True)


def test_ct25_usuario_ve_mensagem_de_conflito(page: Page, servidor: str):
    dia = proximo_dia_util()
    # Pré-condição: Ana já tem um corte às 14:00 (criado direto pela API).
    clientes = {c["nome"]: c["id"] for c in httpx.get(f"{servidor}/clientes").json()}
    profs = {p["nome"]: p for p in httpx.get(f"{servidor}/profissionais").json()}
    ana = profs["Ana Lima"]
    corte = next(s for s in ana["servicos"] if s["nome"] == "Corte de cabelo")
    criado = httpx.post(
        f"{servidor}/agendamentos",
        json={
            "cliente_id": clientes["João Pereira"],
            "profissional_id": ana["id"],
            "servico_id": corte["id"],
            "inicio": f"{dia.isoformat()}T14:00",
        },
    )
    assert criado.status_code == 201

    page.goto("/")
    preencher(page, "Pedro Alves", "Ana Lima", "Corte de cabelo (30 min)", dia, "14:00")
    page.click("#agendar")

    mensagem = page.locator("#mensagem")
    expect(mensagem).to_have_class("mensagem erro")
    expect(mensagem).to_contain_text("O profissional já possui um agendamento neste horário.")
    page.screenshot(path=f"{PRINTS}/ct25_conflito.png", full_page=True)


def test_agendamento_aparece_na_lateral_do_cliente(page: Page):
    dia = proximo_dia_util()
    page.goto("/")
    preencher(page, "Maria Souza", "Ana Lima", "Coloração (90 min)", dia, "15:00")
    page.click("#agendar")
    expect(page.locator("#mensagem")).to_have_class("mensagem sucesso")

    maria = page.locator("#lista-clientes .cliente", has_text="Maria Souza")
    expect(maria.locator(".horario", has_text=f"{dia:%d/%m/%Y} · 15:00–16:30")).to_contain_text(
        "Coloração com Ana Lima"
    )


def test_usuario_adiciona_cliente_pelo_botao_lateral(page: Page):
    page.goto("/")
    expect(page.locator("#novo-cliente")).to_be_hidden()

    page.click("#abrir-cliente")
    page.fill("#cliente-nome", "Lucas Félix")
    page.fill("#cliente-telefone", "48912345678")
    page.click("#salvar-cliente")

    expect(page.locator("#mensagem-cliente")).to_have_text("Cliente Lucas Félix cadastrado.")
    expect(page.locator("#novo-cliente")).to_be_hidden()
    # aparece na lateral e já fica selecionado no formulário de agendamento
    novo = page.locator("#lista-clientes .cliente", has_text="Lucas Félix")
    expect(novo).to_contain_text("(48) 91234-5678")
    expect(novo).to_contain_text("Sem horários agendados")
    expect(page.locator("#cliente option:checked")).to_have_text("Lucas Félix")
    page.screenshot(path=f"{PRINTS}/novo_cliente.png", full_page=True)


def test_cadastro_de_cliente_invalido_mostra_erro(page: Page):
    page.goto("/")
    page.click("#abrir-cliente")
    page.fill("#cliente-nome", "Teste")
    page.fill("#cliente-telefone", "1234")
    page.click("#salvar-cliente")

    erro = page.locator("#mensagem-cliente")
    expect(erro).to_have_class("mensagem erro")
    expect(erro).to_contain_text("telefone deve ter DDD")
    expect(page.locator("#novo-cliente")).to_be_visible()  # formulário continua aberto para corrigir
