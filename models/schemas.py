"""
Esquemas Pydantic para validar y estructurar los payloads entrantes
del Webhook oficial de WhatsApp Business Cloud API (Meta).
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class WhatsAppText(BaseModel):
    """Contenido de un mensaje de tipo texto."""

    body: str


class WhatsAppMedia(BaseModel):
    """Metadatos básicos de un archivo multimedia (imagen o documento) enviado por el cliente."""

    model_config = ConfigDict(extra="ignore")

    id: str
    mime_type: Optional[str] = None
    caption: Optional[str] = None
    filename: Optional[str] = None


class WhatsAppProfile(BaseModel):
    """Perfil público del contacto en WhatsApp."""

    name: Optional[str] = None


class WhatsAppContact(BaseModel):
    """Información del contacto remitente."""

    wa_id: str
    profile: Optional[WhatsAppProfile] = None


class WhatsAppMessage(BaseModel):
    """Representa un mensaje individual recibido en el webhook."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(..., description="ID único del mensaje en WhatsApp (wamid)")
    from_: str = Field(..., alias="from", description="Número de teléfono del remitente")
    timestamp: str
    type: str = Field(..., description="Tipo de mensaje: text, audio, image, document, etc.")
    text: Optional[WhatsAppText] = None
    image: Optional[WhatsAppMedia] = None
    document: Optional[WhatsAppMedia] = None


class WhatsAppStatus(BaseModel):
    """Evento de cambio de estado de un mensaje saliente (sent, delivered, read, failed)."""

    id: str
    status: str
    timestamp: str
    recipient_id: str


class WhatsAppMetadata(BaseModel):
    """Metadatos del número de empresa que recibe el evento."""

    display_phone_number: str
    phone_number_id: str


class WhatsAppValue(BaseModel):
    """Contenedor principal de datos del evento en `changes[].value`."""

    model_config = ConfigDict(extra="ignore")

    messaging_product: str
    metadata: WhatsAppMetadata
    contacts: Optional[list[WhatsAppContact]] = None
    messages: Optional[list[WhatsAppMessage]] = None
    statuses: Optional[list[WhatsAppStatus]] = None
    errors: Optional[list[dict[str, Any]]] = None


class WhatsAppChange(BaseModel):
    """Cambio reportado dentro de una entrada del webhook."""

    field: str
    value: WhatsAppValue


class WhatsAppEntry(BaseModel):
    """Entrada individual del lote de eventos de Meta."""

    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Estructura raíz del payload enviado por Meta al endpoint POST /webhook."""

    model_config = ConfigDict(extra="ignore")

    object: str
    entry: list[WhatsAppEntry]


class IncomingUserMessage(BaseModel):
    """DTO interno limpio con los datos extraídos listos para el worker en background."""

    message_id: str
    sender_phone: str
    sender_name: Optional[str] = None
    text_body: str
    phone_number_id: str

