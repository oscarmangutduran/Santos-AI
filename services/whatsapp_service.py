"""
Servicio asíncrono de integración con WhatsApp Business Cloud API (Meta).
Utiliza `httpx.AsyncClient` con manejo defensivo de errores y timeouts.
"""

import logging
from typing import Any, Optional
import httpx

from config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Cliente asíncrono para enviar mensajes y actualizar estados en WhatsApp Cloud API."""

    def __init__(self) -> None:
        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        self._timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS, connect=5.0)

    async def mark_as_read(self, message_id: str) -> bool:
        """
        Marca un mensaje entrante como leído (doble check azul) en WhatsApp.
        Falla de forma silenciosa (logged) para no interrumpir el flujo principal.
        """
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    settings.whatsapp_messages_url,
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                logger.debug("Mensaje %s marcado como leído en WhatsApp.", message_id)
                return True
        except httpx.TimeoutException:
            logger.warning("Timeout al marcar como leído el mensaje %s en Meta.", message_id)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Error HTTP %s de Meta al marcar como leído %s: %s",
                exc.response.status_code,
                message_id,
                exc.response.text,
            )
        except httpx.RequestError as exc:
            logger.error("Error de red al conectar con Meta API (mark_as_read): %s", exc)

        return False

    async def send_text_message(
        self,
        recipient_phone: str,
        text: str,
        preview_url: bool = False,
    ) -> Optional[str]:
        """
        Envía un mensaje de texto al número de WhatsApp indicado.
        Retorna el `wamid` asignado por Meta si tuvo éxito, o `None` en caso de fallo.
        """
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": text,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    settings.whatsapp_messages_url,
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                messages = data.get("messages", [])
                sent_wamid: Optional[str] = messages[0].get("id") if messages else None
                logger.info(
                    "Respuesta enviada a %s (wamid=%s).",
                    recipient_phone,
                    sent_wamid,
                )
                return sent_wamid

        except httpx.TimeoutException:
            logger.error(
                "Timeout (%ss) al enviar mensaje de WhatsApp a %s.",
                settings.HTTP_TIMEOUT_SECONDS,
                recipient_phone,
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Error HTTP %s de Meta al enviar mensaje a %s: %s",
                exc.response.status_code,
                recipient_phone,
                exc.response.text,
            )
        except httpx.RequestError as exc:
            logger.error(
                "Error de red al intentar enviar mensaje de WhatsApp a %s: %s",
                recipient_phone,
                exc,
            )

        return None


whatsapp_service = WhatsAppService()

