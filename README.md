# Sistema de Agendamento com Testes Automatizados

Trabalho da disciplina **Qualidade e Teste de Software** (UNESC, Prof. Riciere Massariol).

API de agendamento de serviços para um salão (FastAPI + SQLite), testada em três camadas:
**unitária**, **API** e **ponta a ponta (E2E)** no navegador.

## Instalação

Requer Python 3.12 ou superior.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # navegador dos testes E2E
```

## Rodar a aplicação

```bash
uvicorn app.main:app --reload
```

- Formulário de agendamento: http://127.0.0.1:8000/
- Documentação automática da API: http://127.0.0.1:8000/docs

Na primeira execução o banco `agendamento.db` é criado com dados de exemplo
(3 profissionais, 4 serviços, 3 clientes — ver `app/seed.py`).

## Rodar os testes

| Comando | O que faz |
| --- | --- |
| `pytest` | Roda tudo (unit + API + E2E) |
| `pytest -m unit` | Só os unitários (regras de negócio) |
| `pytest -m api` | Só os de API |
| `pytest -m e2e --video=on` | Só os E2E, gravando vídeo em `test-results/` |
| `pytest -m e2e --headed --slowmo 500` | E2E com o navegador visível, em câmera lenta |
| `pytest --cov=app --cov-report=html` | Relatório de cobertura em `htmlcov/index.html` |

O GitHub Actions (`.github/workflows/testes.yml`) roda todas as camadas a cada push,
exige cobertura mínima de 85% e publica cobertura, vídeos e prints como artefato.

## Regras de negócio

| RN | Regra | Onde |
| --- | --- | --- |
| RN01 | Fim = início + duração do serviço | `calcular_fim` |
| RN02 | Começar e terminar dentro do expediente | `validar_expediente` |
| RN03 | Só nos dias de trabalho do profissional | `validar_dia_trabalho` |
| RN04 | Agendamentos ativos do profissional não se sobrepõem | `validar_conflito_profissional` |
| RN05 | Encostar não é conflito (10:00–10:30 e 10:30–11:00) | `ha_sobreposicao` |
| RN06 | Não agendar no passado | `validar_antecedencia` |
| RN07 | Antecedência mínima de 1 hora | `validar_antecedencia` |
| RN08 | Cancelar só com 24h de antecedência | `pode_cancelar` |
| RN09 | Profissional habilitado para o serviço | `validar_habilitacao` |
| RN10 | Cliente não pode estar em dois lugares ao mesmo tempo | `validar_conflito_cliente` |
| RN11 | Início em múltiplos de 15 minutos | `validar_grade_horario` |

Todas ficam em `app/regras.py` como funções puras: não acessam banco, HTTP nem relógio
(o "agora" chega por parâmetro). Transições de estado permitidas: `ativo → cancelado` e
`ativo → concluido`.

## Endpoints

| Método e rota | Descrição |
| --- | --- |
| `POST /agendamentos` | Cria um agendamento (201; 400 regra violada; 409 conflito; 422 dados inválidos) |
| `GET /agendamentos?profissional=&data=` | Agenda do profissional no dia |
| `GET /agendamentos/{id}` | Consulta um agendamento |
| `PATCH /agendamentos/{id}/cancelar` | Cancela (RN08) |
| `PATCH /agendamentos/{id}/concluir` | Marca como concluído |
| `GET /disponibilidade?profissional=&servico=&data=` | Horários de início livres |
| `GET /profissionais`, `/servicos`, `/clientes` | Cadastros (usados pelo formulário) |

Erros de regra de negócio retornam `{"detail": "mensagem", "regra": "RN04"}`.

## Decisões de projeto

- **Horário local, sem fuso.** Datas com fuso (`2026-11-17T10:00-03:00`) são recusadas com 422.
- **Relógio controlado nos testes.** Nos testes de API o `freezegun` congela o relógio em
  segunda-feira, 16/11/2026, 08:00. Os testes E2E rodam a aplicação em outro processo, onde o
  freezegun não alcança; por isso usam datas relativas (próximo dia útil, ao menos 2 dias à frente).
- **Banco isolado por teste.** Cada teste de API recebe um SQLite em memória novo.

## Estrutura

```
app/        aplicação (regras.py é o núcleo testável)
tests/
  unit/     regras de negócio isoladas
  api/      endpoints com TestClient + banco em memória
  e2e/      navegador com Playwright
```
