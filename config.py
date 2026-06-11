import os
from dotenv import load_dotenv

load_dotenv()

#DISCORD
DISCORD_CLIENT_ID: str = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET: str = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI: str = os.getenv("REDIRECT_URI")
#REDIRECT_URI: str = "http://localhost:8080/callback"
SESSION_SECRET: str = os.getenv("SESSION_SECRET")
API_ENDPOINT: str = os.getenv("API_ENDPOINT")

#BASES DE DATOS
URL_BASE_1: str = os.getenv("URL_BASE_1")

#TOKEN
BOT: str = os.getenv("BOT")
PREFIX: str = os.getenv("PREFIX")
BOT_LINK: str = os.getenv("BOT_LINK")

#CANALES
def _int_env(name: str, default: int = 0) -> int:
    """Lee una variable de entorno como entero sin reventar el arranque si falta o es inválida."""
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        print(f"[config] Aviso: la variable de entorno '{name}' no está definida; se usa {default}.")
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[config] Aviso: '{name}'='{raw}' no es un entero válido; se usa {default}.")
        return default

ERROR_CHANNEL: int = _int_env("ERROR_CHANNEL")
LOG_CHANNEL: int = _int_env("LOG_CHANNEL")
BUG_CHANNEL: int = _int_env("BUG_CHANNEL")
SERVER_LOG_CHANNEL: int = _int_env("SERVER_LOG_CHANNEL")
SUGGESTION_CHANNEL: int = _int_env("SUGGESTION_CHANNEL")


#DOCUMENTACION
DOC_URL: str = os.getenv("DOC_URL")
_owner_id = _int_env("OWNER")
OWNER = [_owner_id] if _owner_id else []

# (Obsoleto) El loop de reportes ahora corre cada 15s y la entrega desde el bot es inmediata.
# Se mantiene por compatibilidad; ya no se usa.
LOOP_TIME: int = 60