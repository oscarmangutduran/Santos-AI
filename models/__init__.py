"""Paquete de modelos de datos y esquemas de validación."""

from models.database import (
    ConversationMessage,
    close_db,
    get_recent_conversation_history,
    init_db,
    is_message_already_processed,
    save_message,
)
from models.schemas import IncomingUserMessage, WhatsAppWebhookPayload

__all__ = [
    "ConversationMessage",
    "IncomingUserMessage",
    "WhatsAppWebhookPayload",
    "close_db",
    "get_recent_conversation_history",
    "init_db",
    "is_message_already_processed",
    "save_message",
]

