import requests
from typing import Optional, List, Dict
from config import API_ENDPOINT, BOT as BOT_TOKEN

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
        Realiza una petición a la API de Discord con timeout y manejo de errores de red.
        Devuelve el objeto Response, o None si no hay token o la conexión falla.
        """
        if not BOT_TOKEN:
            return None
        try:
            return requests.request(
                method, url,
                headers=DiscordAPI.get_headers(),
                timeout=DEFAULT_TIMEOUT,
                **kwargs
            )
        except requests.RequestException as e:
            print(f"[DiscordAPI] Error de red en {method} {url}: {e}")
            return None

    @staticmethod
    def get_bot_guilds() -> List[Dict]:
        """
        Obtiene todos los servidores donde está el bot
        """
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
        return guilds

    @staticmethod
    def get_guild(guild_id: str) -> Optional[Dict]:
        """
        Obtiene información de un servidor
        """
        res = DiscordAPI._request("GET", f"{API_ENDPOINT}/guilds/{guild_id}?with_counts=true")
        return res.json() if res and res.status_code == 200 else None

    @staticmethod
    def get_guild_member(guild_id: str, user_id: str) -> Optional[Dict]:
        """
        Obtiene información de un miembro de un servidor
        """
        res = DiscordAPI._request("GET", f"{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}")
        return res.json() if res and res.status_code == 200 else None

    @staticmethod
    def get_guild_channels(guild_id: str) -> List[Dict]:
        """
        Obtiene los canales de un servidor
        """
        res = DiscordAPI._request("GET", f"{API_ENDPOINT}/guilds/{guild_id}/channels")
        return res.json() if res and res.status_code == 200 else []

    @staticmethod
    def get_guild_roles(guild_id: str) -> List[Dict]:
        """
        Obtiene los roles de un servidor
        """
        res = DiscordAPI._request("GET", f"{API_ENDPOINT}/guilds/{guild_id}/roles")
        return res.json() if res and res.status_code == 200 else []

    @staticmethod
    def get_user(user_id: str) -> Optional[Dict]:
        """
        Obtiene información de un usuario
        """
        res = DiscordAPI._request("GET", f"{API_ENDPOINT}/users/{user_id}")
        return res.json() if res and res.status_code == 200 else None

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
