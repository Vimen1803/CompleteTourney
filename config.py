import os
from dotenv import load_dotenv

load_dotenv()

#DISCORD
DISCORD_CLIENT_ID: str = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET: str = os.getenv("DISCORD_CLIENT_SECRET")
# REDIRECT_URI: str = os.getenv("REDIRECT_URI")
REDIRECT_URI: str = "http://localhost:8080/callback"
SESSION_SECRET: str = os.getenv("SESSION_SECRET")
API_ENDPOINT: str = os.getenv("API_ENDPOINT")

#BASES DE DATOS
URL_BASE_1: str = os.getenv("URL_BASE_1")

#TOKEN
BOT: str = os.getenv("BOT")
PREFIX: str = os.getenv("PREFIX")
BOT_LINK: str = os.getenv("BOT_LINK")

#CANALES
ERROR_CHANNEL: int = int(os.getenv("ERROR_CHANNEL"))
LOG_CHANNEL: int = int(os.getenv("LOG_CHANNEL"))
BUG_CHANNEL: int = int(os.getenv("BUG_CHANNEL"))
SERVER_LOG_CHANNEL: int = int(os.getenv("SERVER_LOG_CHANNEL"))
SUGGESTION_CHANNEL: int = int(os.getenv("SUGGESTION_CHANNEL"))


#DOCUMENTACION
DOC_URL: str = os.getenv("DOC_URL")
OWNER = [int(os.getenv("OWNER"))]

LOOP_TIME: int = 60