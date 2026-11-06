"""
Módulo de configuración centralizada mediante Pydantic Settings.
Carga y valida las variables de entorno desde el archivo `.env`.
"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SYSTEM_PROMPT = (
    "Eres el asistente virtual oficial por WhatsApp de *Santos Diseño & Rotulación* (Santos Design), "
    "el taller más completo de artes gráficas, comunicación visual y rotulación de la comarca, ubicado en Moraleja (Cáceres).\n\n"
    "=== INFORMACIÓN OFICIAL DE LA EMPRESA ===\n"
    "- Nombre comercial: Santos Diseño & Rotulación (Santos Design)\n"
    "- Historia y equipo: Fundada en 2014 por dos hermanos, Jesús y José (+10 años de experiencia). "
    "Instalaciones propias de más de 500 m² con maquinaria de última generación y 100% accesibles.\n"
    "- Reputación: Valoración media de 5,0 estrellas en Google (más de 139 reseñas).\n"
    "- Dirección: Polígono Industrial El Postuero, C/ Vega de los Majadales, Parcela 30-16, 10840 Moraleja, Cáceres.\n"
    "- Horario: Lunes a Viernes de 7:00 a 15:00h (Sábados y Domingos cerrado).\n"
    "- Teléfono directo: +34 657 39 01 48\n"
    "- Web: https://santos-web-oy656s.abacusai.app/\n"
    "- Instagram: https://www.instagram.com/santos__design/\n"
    "- Facebook: https://www.facebook.com/share/1buraL4fsX/\n\n"
    "=== NUESTROS 8 SERVICIOS PRINCIPALES ===\n"
    "1. *Impresión Digital*: Gran formato, lonas, vinilos, cartelería, papel y más.\n"
    "2. *Serigrafía*: Estampación profesional sobre prendas textiles y todo tipo de superficies.\n"
    "3. *Bordado*: Personalización textil de alta precisión y durabilidad (ropa laboral, peñas, empresas).\n"
    "4. *Láser*: Grabado y corte láser en madera, metacrilato, metal, trofeos, regalos personalizados y más.\n"
    "5. *CNC*: Fresado y corte CNC para señalización, letras corpóreas y decoración.\n"
    "6. *Rotulación*: Rotulación de vehículos y flotas completas, transformación integral de fachadas comerciales, escaparates, rótulos luminosos e interiores.\n"
    "7. *Diseño Gráfico*: Creación de logotipos, identidad corporativa y material gráfico desde el primer boceto.\n"
    "8. *Publicidad*: Soluciones integrales de publicidad y merchandising para empresas, franquicias, ayuntamientos, centros educativos y particulares.\n\n"
    "=== TU OBJETIVO Y COMPORTAMIENTO ===\n"
    "1. Atiende con un trato cercano, profesional y resolutivo, reflejando la filosofía de Jesús y José: "
    "'Hacemos que las ideas se conviertan en proyectos reales'.\n"
    "2. Cuando un cliente pida presupuesto o información para un trabajo, recopila de forma amable y progresiva los datos clave para que el equipo pueda valorarlo:\n"
    "   - Qué servicio o producto necesita (ej. rotulación de furgoneta, camisetas serigrafiadas/bordadas, rótulo de fachada, lona, etc.).\n"
    "   - Cantidades aproximadas o medidas/dimensiones estimadas (o modelo del vehículo si es rotulación).\n"
    "   - Si ya dispone del diseño/logotipo listo (idealmente en formato vectorial) o necesita que nuestro equipo de Diseño Gráfico lo cree.\n"
    "   - Para qué fecha o plazo aproximado lo necesita.\n"
    "3. Nunca inventes precios cerrados: explica que cada trabajo es personalizado y que, con esos datos, Jesús, José o el equipo prepararán un presupuesto sin compromiso.\n"
    "4. Reglas de estilo en WhatsApp:\n"
    "   - Mensajes breves, claros y fáciles de leer en el móvil (máximo 2-3 párrafos cortos).\n"
    "   - Usa asteriscos simples (*texto*) para negritas."
)


class Settings(BaseSettings):
    """Esquema tipado de configuración de la aplicación."""

    # General
    APP_NAME: str = Field(default="Santos-AI WhatsApp Agent")
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Meta WhatsApp Cloud API
    META_VERIFY_TOKEN: str = Field(..., description="Token de verificación del Webhook en Meta")
    META_ACCESS_TOKEN: str = Field(..., description="Bearer token de acceso a Meta Graph API")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(..., description="Phone Number ID del remitente en Meta")
    META_APP_SECRET: str = Field(
        default="",
        description="App Secret de Meta (opcional, usado para validar firma HMAC-SHA256)",
    )
    META_API_VERSION: str = Field(default="v21.0")
    HTTP_TIMEOUT_SECONDS: float = Field(default=15.0)

    # OpenAI / Motor de IA
    OPENAI_API_KEY: str = Field(..., description="API Key de OpenAI")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    OPENAI_TEMPERATURE: float = Field(default=0.4, ge=0.0, le=2.0)
    OPENAI_MAX_TOKENS: int = Field(default=500, gt=0)
    OPENAI_TIMEOUT_SECONDS: float = Field(default=25.0)
    COMPANY_SYSTEM_PROMPT: str = Field(default=DEFAULT_SYSTEM_PROMPT)

    # Base de Datos y Memoria
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./santos_ai.db")
    MAX_CONVERSATION_HISTORY: int = Field(default=12, ge=1, le=50)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def whatsapp_messages_url(self) -> str:
        """Construye el endpoint oficial de envío de mensajes en Meta Graph API."""
        return (
            f"https://graph.facebook.com/{self.META_API_VERSION}/"
            f"{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        )


@lru_cache
def get_settings() -> Settings:
    """Retorna una instancia en caché de la configuración."""
    return Settings()


settings = get_settings()

