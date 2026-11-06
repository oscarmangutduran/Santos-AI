# Santos-AI — Agente de IA para WhatsApp (Santos Diseño & Rotulación)

Backend asíncrono en **FastAPI** conectado a la **WhatsApp Business Cloud API oficial de Meta** y **OpenAI** para responder automáticamente a clientes de **Santos Diseño & Rotulación** (Moraleja, Cáceres — https://santos-web-oy656s.abacusai.app/).

## Características Principales
- **Respuesta inmediata a Meta (`HTTP 200 OK`)**: Procesamiento desacoplado con `BackgroundTasks` en [`routers/webhook.py`](routers/webhook.py).
- **Conocimiento real del negocio**: System Prompt preconfigurado en [`config.py`](config.py) con los 8 servicios del taller (Impresión Digital, Serigrafía, Bordado, Láser, CNC, Rotulación, Diseño Gráfico y Publicidad), horario (L–V de 7:00 a 15:00h), ubicación en el Polígono Industrial El Postuero (Moraleja, Cáceres) y teléfono (+34 657 39 01 48).
- **Memoria conversacional e idempotencia**: Persistencia asíncrona por número de teléfono y control de mensajes duplicados (`wamid`) mediante SQLAlchemy 2.0 + SQLite/PostgreSQL en [`models/database.py`](models/database.py).
- **Filtrado defensivo**: Ignora eventos de estado (`sent`, `delivered`, `read`, `failed`) y evita bucles de auto-respuesta.
