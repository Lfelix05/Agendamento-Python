"""Sobe a aplicação de verdade (uvicorn) para o Playwright usar no navegador.

O servidor roda em outro processo, com um banco SQLite temporário. Como o
freezegun não alcança outro processo, os testes E2E usam datas relativas ao
dia real (sempre um dia útil, pelo menos dois dias à frente), o que mantém o
resultado determinístico em relação às regras RN03, RN06 e RN07.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright")

RAIZ = Path(__file__).resolve().parents[2]


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor(tmp_path_factory):
    porta = _porta_livre()
    banco = tmp_path_factory.mktemp("e2e") / "e2e.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{banco.as_posix()}"}
    processo = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(porta)],
        cwd=RAIZ,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{porta}"
    try:
        for _ in range(100):  # até ~10 s para subir
            try:
                if httpx.get(f"{url}/clientes").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        else:
            pytest.fail("O servidor da aplicação não subiu a tempo.")
        yield url
    finally:
        processo.terminate()
        processo.wait(timeout=10)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """Campos de data/hora nativos seguem o idioma do navegador, não o ``locale``."""
    args = [*browser_type_launch_args.get("args", []), "--lang=pt-BR"]
    return {**browser_type_launch_args, "args": args}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Navegador em português: datas dd/mm/aaaa e horário 24h nos prints e vídeos."""
    return {**browser_context_args, "locale": "pt-BR", "timezone_id": "America/Sao_Paulo"}


@pytest.fixture(scope="session")
def base_url(servidor):
    """Faz ``page.goto("/")`` apontar para o servidor de teste."""
    return servidor
