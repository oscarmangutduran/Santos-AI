"""
Servicio del Agente de IA.
Gestiona la memoria conversacional por cliente, construye el contexto con el System Prompt
y realiza llamadas asíncronas a OpenAI con manejo defensivo de excepciones.
"""

import logging
from typing import Optional
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from sqlalchemy.exc import IntegrityError

from config import settings
from models.database import (
    get_recent_conversation_history,
    is_message_already_processed,
    save_message,
)
from models.schemas import IncomingUserMessage
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

FALLBACK_ERROR_MESSAGE = (
    "Disculpa, en este momento estamos experimentando una alta demanda en nuestro sistema automático. "
    "Por favor, déjanos los detalles de tu consulta por aquí o llámanos al *+34 657 39 01 48* "
    "(Lunes a Viernes de 7:00 a 15:00h) y el equipo de *Santos Diseño & Rotulación* te atenderá enseguida."
)


class AIAgentService:
    """Orquestador de generación de respuestas con IA y persistencia de contexto."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
            max_retries=2,
        )

    def _build_system_prompt(self, sender_name: Optional[str]) -> str:
        """Enriquece el System Prompt de la empresa con el nombre del cliente si está disponible."""
        base_prompt = settings.COMPANY_SYSTEM_PROMPT
        if sender_name:
            return (
                f"{base_prompt}\n\n"
                f"Contexto del usuario actual: El perfil de WhatsApp del cliente se llama '{sender_name}'."
            )
        return base_prompt

    async def generate_reply(
        self,
        phone_number: str,
        user_text: str,
        sender_name: Optional[str] = None,
        whatsapp_message_id: Optional[str] = None,
    ) -> str:
        """
        1. Persiste el mensaje entrante del usuario.
        2. Recupera los últimos N mensajes de la conversación.
        3. Invoca de forma asíncrona a OpenAI Chat Completions.
        4. Persiste y retorna la respuesta generada.
        """
        # Guardar el mensaje entrante en la base de datos
        await save_message(
            phone_number=phone_number,
            role="user",
            content=user_text,
            contact_name=sender_name,
            whatsapp_message_id=whatsapp_message_id,
        )

        # Recuperar historial reciente (incluye el mensaje recién guardado al final)
        history = await get_recent_conversation_history(
            phone_number=phone_number,
            limit=settings.MAX_CONVERSATION_HISTORY,
        )

        messages_payload: list[dict[str, str]] = [
            {"role": "system", "content": self._build_system_prompt(sender_name)},
            *history,
        ]

        try:
            response = await self._client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages_payload,  # type: ignore[arg-type]
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
            )
            reply_text = (response.choices[0].message.content or "").strip()
            if not reply_text:
                reply_text = FALLBACK_ERROR_MESSAGE

        except APITimeoutError:
            logger.error("Timeout de OpenAI al generar respuesta para %s.", phone_number)
            return FALLBACK_ERROR_MESSAGE
        except APIConnectionError as exc:
            logger.error("Error de conexión con OpenAI para %s: %s", phone_number, exc)
            return FALLBACK_ERROR_MESSAGE
        except APIStatusError as exc:
            logger.error(
                "Error de estado de OpenAI (HTTP %s) para %s: %s",
                exc.status_code,
                phone_number,
                exc.message,
            )
            return FALLBACK_ERROR_MESSAGE
        except Exception as exc:
            logger.exception("Error inesperado en AIAgentService para %s: %s", phone_number, exc)
            return FALLBACK_ERROR_MESSAGE

        # Persistir la respuesta del asistente en el historial
        await save_message(
            phone_number=phone_number,
            role="assistant",
            content=reply_text,
            contact_name=sender_name,
        )

        return reply_text

    async def process_incoming_whatsapp_message(self, incoming: IncomingUserMessage) -> None:
        """
        Worker asíncrono ejecutado en BackgroundTasks:
        - Verifica idempotencia por `wamid`.
        - Marca el mensaje como leído en WhatsApp.
        - Genera respuesta con el LLM.
        - Envía la respuesta al usuario por WhatsApp Cloud API.
        """
        try:
            if await is_message_already_processed(incoming.message_id):
                logger.info(
                    "Mensaje duplicado ignorado (wamid=%s de %s).",
                    incoming.message_id,
                    incoming.sender_phone,
                )
                return

            # 1. Marcar mensaje como leído para dar feedback inmediato al cliente
            await whatsapp_service.mark_as_read(incoming.message_id)

            # 2. Generar respuesta contextual con OpenAI
            reply_text = await self.generate_reply(
                phone_number=incoming.sender_phone,
                user_text=incoming.text_body,
                sender_name=incoming.sender_name,
                whatsapp_message_id=incoming.message_id,
            )

            # 3. Enviar mensaje de respuesta a través de Meta Graph API
            await whatsapp_service.send_text_message(
                recipient_phone=incoming.sender_phone,
                text=reply_text,
            )

        except IntegrityError:
            logger.warning(
                "Condición de carrera evitada para wamid=%s (ya procesado).",
                incoming.message_id,
            )
        except Exception as exc:
            logger.exception(
                "Fallo crítico procesando mensaje en segundo plano (wamid=%s): %s",
                incoming.message_id,
                exc,
            )


ai_agent_service = AIAgentService()

