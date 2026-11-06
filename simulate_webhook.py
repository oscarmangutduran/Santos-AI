"""
Script de prueba local para simular llamadas de Meta WhatsApp Cloud API al backend Santos-AI.
Permite probar:
1. GET /webhook (Verificación del Challenge de Meta).
2. POST /webhook con evento de estado 'delivered' (debe ser ignorado sin disparar IA).
3. POST /webhook con un mensaje de texto real de un cliente solicitando presupuesto a Santos Diseño & Rotulación.
"""

import asyncio
import time
import httpx

from config import settings

BASE_URL = "http://localhost:8000"


async def test_webhook_Flow() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        print("1. Probando GET /health ...")
        resp_health = await client.get("/health")
        print(f"   Status: {resp_health.status_code} | Respuesta: {resp_health.json()}\n")

        print("2. Probando GET /webhook (Challenge Verification de Meta) ...")
        challenge_code = "192837465"
        resp_verify = await client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.META_VERIFY_TOKEN,
                "hub.challenge": challenge_code,
            },
        )
        print(f"   Status: {resp_verify.status_code} | Challenge devuelto: {resp_verify.text}\n")

        print("3. Probando POST /webhook con evento de ESTADO ('delivered') -> debe ignorarse ...")
        status_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1029384756",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "34657390148",
                                    "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.STATUS_TEST_001",
                                        "status": "delivered",
                                        "timestamp": str(int(time.time())),
                                        "recipient_id": "34600112233",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        resp_status = await client.post("/webhook", json=status_payload)
        print(f"   Status: {resp_status.status_code} | Respuesta: {resp_status.json()}\n")

        print("4. Probando POST /webhook con MENSAJE DE CLIENTE real ...")
        message_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1029384756",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "34657390148",
                                    "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Carlos Gómez"},
                                        "wa_id": "34600112233",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "34600112233",
                                        "id": f"wamid.MSG_TEST_{int(time.time())}",
                                        "timestamp": str(int(time.time())),
                                        "type": "text",
                                        "text": {
                                            "body": (
                                                "Hola buenas! Quería pedir presupuesto para rotular una "
                                                "furgoneta de empresa y bordar 25 polos con nuestro logo."
                                            )
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        resp_msg = await client.post("/webhook", json=message_payload)
        print(f"   Status: {resp_msg.status_code} | Respuesta inmediata a Meta: {resp_msg.json()}")
        print("   (Revisa los logs de la consola de Uvicorn para ver el procesamiento en BackgroundTasks).")


if __name__ == "__main__":
    asyncio.run(test_webhook_Flow())

