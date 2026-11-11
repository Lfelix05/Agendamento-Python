"""Tabelas SQLAlchemy: Profissional, Servico, Cliente e Agendamento."""

from datetime import datetime, time

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Table, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.regras import DadosProfissional, Periodo, Status

profissional_servico = Table(
    "profissional_servico",
    Base.metadata,
    Column("profissional_id", ForeignKey("profissionais.id"), primary_key=True),
    Column("servico_id", ForeignKey("servicos.id"), primary_key=True),
)


class Servico(Base):
    __tablename__ = "servicos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    duracao_min: Mapped[int]
    preco: Mapped[float] = mapped_column(Numeric(10, 2))


class Profissional(Base):
    __tablename__ = "profissionais"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    inicio_expediente: Mapped[time] = mapped_column(Time)
    fim_expediente: Mapped[time] = mapped_column(Time)
    # dias da semana no formato weekday() separados por vírgula: "0,1,2,3,4,5" = seg–sáb
    dias_trabalho: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4,5")
    servicos: Mapped[list[Servico]] = relationship(secondary=profissional_servico)

    @property
    def dias(self) -> frozenset[int]:
        return frozenset(int(d) for d in self.dias_trabalho.split(",") if d.strip())

    def dados_regras(self) -> DadosProfissional:
        """Converte a linha do banco para o formato puro usado em ``regras.py``."""
        return DadosProfissional(
            abertura=self.inicio_expediente,
            fechamento=self.fim_expediente,
            dias_trabalho=self.dias,
            servicos_habilitados=frozenset(s.id for s in self.servicos),
        )


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    telefone: Mapped[str] = mapped_column(String(20))


class Agendamento(Base):
    __tablename__ = "agendamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"))
    servico_id: Mapped[int] = mapped_column(ForeignKey("servicos.id"))
    inicio: Mapped[datetime] = mapped_column(DateTime, index=True)
    fim: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default=Status.ATIVO.value)

    cliente: Mapped[Cliente] = relationship()
    profissional: Mapped[Profissional] = relationship()
    servico: Mapped[Servico] = relationship()

    def periodo(self) -> Periodo:
        return Periodo(self.inicio, self.fim, Status(self.status))
