"""
Router de Webhooks para WhatsApp Business Cloud API (Meta).
Incluye:
- GET /webhook: Verificación inicial del Webhook (Challenge de Meta).
- POST /webhook: Recepción asíncrona de eventos, filtrado de estados y despacho a BackgroundTasks.
"""

import hashlib
import hmac
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

from config import settings
from models.schemas import IncomingUserMessage, WhatsAppWebhookPayload
from services.ai_agent import ai_agent_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WhatsApp Webhook"])


def _verify_meta_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Valida la firma HMAC-SHA256 (`X-Hub-Signature-256`) enviada por Meta
    cuando `META_APP_SECRET` está configurado en el entorno.
    """
    if not settings.META_APP_SECRET:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_sig = hmac.new(
        key=settings.META_APP_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    received_sig = signature_header.split("sha256=", 1)[1]
    return hmac.compare_digest(expected_sig, received_sig)


@router.get(
    "/webhook",
    summary="Verificación de Webhook de Meta (Challenge)",
    response_class=PlainTextResponse,
)
async def verify_webhook(
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    """
    Endpoint invocado por Meta al registrar o verificar el Webhook en el panel de desarrolladores.
    Debe responder con el valor plano de `hub.challenge` y código HTTP 200.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        if hub_challenge is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Falta el parámetro hub.challenge",
            )
        logger.info("Webhook de Meta verificado exitosamente.")
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    logger.warning(
        "Fallo en la verificación del Webhook. mode=%s, token_recibido=%s",
        hub_mode,
        hub_verify_token,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Token de verificación inválido o modo no soportado.",
    )


@router.post(
    "/webhook",
    summary="Recepción de eventos y mensajes de WhatsApp",
    status_code=status.HTTP_200_OK,
)
async def receive_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
) -> JSONResponse:
    """
    Recibe notificaciones en tiempo real desde WhatsApp Cloud API.
    - Responde inmediatamente con HTTP 200 OK para evitar reintentos y bloqueos de Meta.
    - Ignora eventos de estado (`sent`, `delivered`, `read`, `failed`) para evitar bucles infinitos.
    - Encola el procesamiento de IA y envío de respuesta en `BackgroundTasks`.
    """
    raw_body = await request.body()

    if not _verify_meta_signature(raw_body, x_hub_signature_256):
        logger.warning("Firma X-Hub-Signature-256 inválida rechazada.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de payload inválida.",
        )

    try:
        json_data = await request.json()
        payload = WhatsAppWebhookPayload.model_validate(json_data)
    except ValidationError as exc:
        # Retornamos 200 OK aún ante esquemas no reconocidos para evitar que Meta deshabilite el webhook
        logger.warning("Payload de Webhook no coincide con el esquema esperado: %s", exc)
        return JSONResponse(
            content={"status": "IGNORED_INVALID_SCHEMA"},
            status_code=status.HTTP_200_OK,
        )
    except Exception as exc:
        logger.error("Error al parsear JSON en POST /webhook: %s", exc)
        return JSONResponse(
            content={"status": "IGNORED_MALFORMED_JSON"},
            status_code=status.HTTP_200_OK,
        )

    if payload.object != "whatsapp_business_account":
        return JSONResponse(
            content={"status": "IGNORED_UNSUPPORTED_OBJECT"},
            status_code=status.HTTP_200_OK,
        )

    for entry in payload.entry:
        for change in entry.changes:
            value = change.value

            # 1. Filtrar actualizaciones de estado (sent, delivered, read, failed)
            if value.statuses:
                logger.debug(
                    "Evento de estado ignorado (%d estados recibidos).",
                    len(value.statuses),
                )
                continue

            # 2. Verificar si existen mensajes entrantes de usuarios
            if not value.messages:
                continue

            # Mapa rápido de wa_id -> nombre de perfil del contacto
            contact_names: dict[str, Optional[str]] = {}
            if value.contacts:
                for contact in value.contacts:
                    contact_names[contact.wa_id] = (
                        contact.profile.name if contact.profile else None
                    )

            for message in value.messages:
                # Evitar posibles auto-bucles si el remitente coincide con el número de la empresa
                if message.from_ == value.metadata.display_phone_number:
                    logger.debug("Mensaje propio ignorado para evitar bucle de auto-respuesta.")
                    continue

                # Extraer texto del mensaje o contexto de archivo adjunto (logos, bocetos, fotos de fachadas/vehículos)
                extracted_text: Optional[str] = None
                if message.type == "text" and message.text and message.text.body.strip():
                    extracted_text = message.text.body.strip()
                elif message.type == "image" and message.image:
                    caption = f" con el comentario: '{message.image.caption}'" if message.image.caption else ""
                    extracted_text = f"[El cliente ha enviado una imagen/foto adjunta{caption}]"
                elif message.type == "document" and message.document:
                    doc_name = f" ('{message.document.filename}')" if message.document.filename else ""
                    caption = f" con el comentario: '{message.document.caption}'" if message.document.caption else ""
                    extracted_text = f"[El cliente ha enviado un documento/diseño adjunto{doc_name}{caption}]"

                if not extracted_text:
                    logger.info(
                        "Mensaje no soportado o vacío ignorado (tipo=%s, de=%s).",
                        message.type,
                        message.from_,
                    )
                    continue

                incoming_dto = IncomingUserMessage(
                    message_id=message.id,
                    sender_phone=message.from_,
                    sender_name=contact_names.get(message.from_),
                    text_body=extracted_text,
                    phone_number_id=value.metadata.phone_number_id,
                )

                logger.info(
                    "Encolando mensaje wamid=%s de %s (%s) en BackgroundTasks.",
                    incoming_dto.message_id,
                    incoming_dto.sender_phone,
                    incoming_dto.sender_name or "Sin nombre",
                )

                background_tasks.add_task(
                    ai_agent_service.process_incoming_whatsapp_message,
                    incoming_dto,
                )

    return JSONResponse(
        content={"status": "EVENT_RECEIVED"},
        status_code=status.HTTP_200_OK,
    )

