"""Dados de exemplo: um salão com três profissionais, quatro serviços e três clientes.

Para trocar o tipo de negócio (clínica, oficina), basta alterar os nomes aqui.
"""

from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cliente, Profissional, Servico

SEG_A_SAB = "0,1,2,3,4,5"
SEG_A_SEX = "0,1,2,3,4"


def popular(db: Session) -> bool:
    """Insere os dados de exemplo se o banco estiver vazio. Retorna True se inseriu."""
    if db.scalar(select(Servico).limit(1)) is not None:
        return False

    corte = Servico(nome="Corte de cabelo", duracao_min=30, preco=50)
    barba = Servico(nome="Barba", duracao_min=30, preco=35)
    coloracao = Servico(nome="Coloração", duracao_min=90, preco=150)
    manicure = Servico(nome="Manicure", duracao_min=45, preco=40)

    db.add_all(
        [
            Profissional(
                nome="Ana Lima",
                inicio_expediente=time(8, 0),
                fim_expediente=time(18, 0),
                dias_trabalho=SEG_A_SAB,
                servicos=[corte, coloracao],
            ),
            Profissional(
                nome="Bruno Costa",
                inicio_expediente=time(8, 0),
                fim_expediente=time(18, 0),
                dias_trabalho=SEG_A_SAB,
                servicos=[corte, barba],
            ),
            Profissional(
                nome="Carla Dias",
                inicio_expediente=time(9, 0),
                fim_expediente=time(17, 0),
                dias_trabalho=SEG_A_SEX,
                servicos=[manicure],
            ),
            Cliente(nome="João Pereira", telefone="(48) 99999-0001"),
            Cliente(nome="Maria Souza", telefone="(48) 99999-0002"),
            Cliente(nome="Pedro Alves", telefone="(48) 99999-0003"),
        ]
    )
    db.commit()
    return True
