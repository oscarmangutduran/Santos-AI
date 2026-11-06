"""
Capa de persistencia asíncrona con SQLAlchemy 2.0.
Almacena el historial de conversación por número de teléfono y controla la idempotencia
de mensajes procesados (evitando respuestas duplicadas ante reintentos de Meta).
"""

from datetime import datetime, timezone
from typing import Optional, Sequence
from sqlalchemy import DateTime, Index, Integer, String, Text, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import settings


class Base(DeclarativeBase):
    """Clase base declarativa para los modelos ORM."""
    pass


class ConversationMessage(Base):
    """
    Historial de mensajes intercambiados con cada cliente (identificado por su teléfono).
    Permite reconstruir la memoria conversacional para el LLM.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="Rol del mensaje: 'user' o 'assistant'",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        unique=True,
        index=True,
        comment="wamid de Meta para trazabilidad e idempotencia",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_conv_phone_created", "phone_number", "created_at"),
    )


# Motor asíncrono y factoría de sesiones
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Crea las tablas en la base de datos si no existen al iniciar la aplicación."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Cierra limpiamente el pool de conexiones de la base de datos."""
    await engine.dispose()


async def is_message_already_processed(wamid: str) -> bool:
    """
    Verifica si un mensaje entrante de WhatsApp (`wamid`) ya fue registrado.
    Meta puede reenviar el mismo webhook si ocurre latencia en la red.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(ConversationMessage.id).where(
            ConversationMessage.whatsapp_message_id == wamid
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


async def save_message(
    phone_number: str,
    role: str,
    content: str,
    contact_name: Optional[str] = None,
    whatsapp_message_id: Optional[str] = None,
) -> ConversationMessage:
    """Persiste un mensaje del usuario o del asistente en la base de datos."""
    async with AsyncSessionLocal() as session:
        msg = ConversationMessage(
            phone_number=phone_number,
            contact_name=contact_name,
            role=role,
            content=content,
            whatsapp_message_id=whatsapp_message_id,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def get_recent_conversation_history(
    phone_number: str,
    limit: int = settings.MAX_CONVERSATION_HISTORY,
) -> list[dict[str, str]]:
    """
    Recupera los últimos `limit` mensajes de un número de teléfono en orden cronológico,
    formateados directamente para la API Chat Completions de OpenAI.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.phone_number == phone_number)
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        records: Sequence[ConversationMessage] = result.scalars().all()

    # Invertimos la lista para que quede en orden cronológico (más antiguo -> más reciente)
    chronological = list(reversed(records))
    return [{"role": row.role, "content": row.content} for row in chronological]

