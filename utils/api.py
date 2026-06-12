import time
import requests
from typing import Optional, List, Dict
from config import API_ENDPOINT, BOT as BOT_TOKEN
from utils.cache import discord_cache

# Timeout en segundos: evita que una llamada lenta/colgada a Discord bloquee el hilo
# indefinidamente (y, bajo carga, agote el pool de hilos del servidor web).
DEFAULT_TIMEOUT = 10


class DiscordAPI:
    @staticmethod
    def get_headers():
        """
        Obtiene los headers para la API de Discord
        """
        return {"Authorization": f"Bot {BOT_TOKEN}"}

    @staticmethod
    def _request(method: str, url: str, **kwargs):
        """
        Realiza una petición a la API de Discord con timeout, manejo de errores de
        red y un reintento ante rate limit (429) respetando Retry-After.
        Devuelve el objeto Response, o None si no hay token o la conexión falla.
        """
        if not BOT_TOKEN:
            return None

        res = None
        for attempt in range(2):
            try:
                res = requests.request(
                    method, url,
                    headers=DiscordAPI.get_headers(),
                    timeout=DEFAULT_TIMEOUT,
                    **kwargs
                )
            except requests.RequestException as e:
                print(f"[DiscordAPI] Error de red en {method} {url}: {e}")
                return None

            # Rate limit: esperar (acotado) y reintentar una vez
            if res.status_code == 429 and attempt == 0:
                try:
                    retry_after = float(res.headers.get("Retry-After", "1"))
                except (TypeError, ValueError):
                    retry_after = 1.0
                print(f"[DiscordAPI] Rate limit (429) en {url}; reintentando en {retry_after:.2f}s")
                time.sleep(min(retry_after, 5))
                continue

            break

        return res

    @staticmethod
    def _cached_get(cache_key: str, url: str, ttl: int, default):
        """GET cacheado: solo cachea respuestas 200 (no cachea fallos)."""
        cached = discord_cache.get(cache_key)
        if cached is not None:
            return cached
        res = DiscordAPI._request("GET", url)
        if res is not None and res.status_code == 200:
            data = res.json()
            discord_cache.set(cache_key, data, ttl)
            return data
        return default

    @staticmethod
    def get_bot_guilds() -> List[Dict]:
        """
        Obtiene todos los servidores donde está el bot (cacheado 60s)
        """
        cached = discord_cache.get("bot_guilds")
        if cached is not None:
            return cached

        guilds = []
        after = "0"
        while True:
            res = DiscordAPI._request("GET", f"{API_ENDPOINT}/users/@me/guilds?limit=200&after={after}")
            if not res or res.status_code != 200:
                break
            data = res.json()
            if not data:
                break
            guilds.extend(data)
            if len(data) < 200:
                break
            after = data[-1]['id']

        # Solo cachear si se obtuvo algo (evita cachear un fallo total)
        if guilds:
            discord_cache.set("bot_guilds", guilds, 60)
        return guilds

    @staticmethod
    def get_guild(guild_id: str) -> Optional[Dict]:
        """
        Obtiene información de un servidor (cacheado 60s)
        """
        return DiscordAPI._cached_get(f"guild:{guild_id}", f"{API_ENDPOINT}/guilds/{guild_id}?with_counts=true", 60, None)

    @staticmethod
    def get_guild_member(guild_id: str, user_id: str) -> Optional[Dict]:
        """
        Obtiene información de un miembro de un servidor (cacheado 30s)
        """
        return DiscordAPI._cached_get(f"member:{guild_id}:{user_id}", f"{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}", 30, None)

    @staticmethod
    def get_guild_channels(guild_id: str) -> List[Dict]:
        """
        Obtiene los canales de un servidor (cacheado 60s)
        """
        return DiscordAPI._cached_get(f"channels:{guild_id}", f"{API_ENDPOINT}/guilds/{guild_id}/channels", 60, [])

    @staticmethod
    def get_guild_roles(guild_id: str) -> List[Dict]:
        """
        Obtiene los roles de un servidor (cacheado 60s)
        """
        return DiscordAPI._cached_get(f"roles:{guild_id}", f"{API_ENDPOINT}/guilds/{guild_id}/roles", 60, [])

    @staticmethod
    def get_user(user_id: str) -> Optional[Dict]:
        """
        Obtiene información de un usuario (cacheado 300s)
        """
        return DiscordAPI._cached_get(f"user:{user_id}", f"{API_ENDPOINT}/users/{user_id}", 300, None)

    @staticmethod
    def get_icon_url(guild_id, icon_hash):
        """
        Obtiene la URL del icono de un servidor
        """
        if not icon_hash: return None
        return f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png?size=1024"

    @staticmethod
    def get_avatar_url(user_id, avatar_hash):
        """
        Obtiene la URL del avatar de un usuario
        """
        if not avatar_hash: return "https://cdn.discordapp.com/embed/avatars/0.png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"

    @staticmethod
    def modify_current_member(guild_id: str, nick: str = None) -> bool:
        """
        Modifica el apodo del bot en un servidor.
        Requiere el permiso CHANGE_NICKNAME.
        """
        payload = {}
        if nick is not None:
            payload["nick"] = nick
        res = DiscordAPI._request("PATCH", f"{API_ENDPOINT}/guilds/{guild_id}/members/@me", json=payload)
        return bool(res and res.status_code == 200)
