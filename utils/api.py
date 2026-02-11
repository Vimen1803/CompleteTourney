import os
import requests
from typing import Optional, List, Dict
from config import API_ENDPOINT, BOT as BOT_TOKEN

class DiscordAPI:
    @staticmethod
    def get_headers():
        """
        Obtiene los headers para la API de Discord
        """
        return {"Authorization": f"Bot {BOT_TOKEN}"}

    @staticmethod
    def get_bot_guilds() -> List[Dict]:
        """
        Obtiene todos los servidores donde está el bot
        """
        if not BOT_TOKEN: return []
        guilds = []
        after = "0"
        try:
            while True:
                res = requests.get(f"{API_ENDPOINT}/users/@me/guilds?limit=200&after={after}", headers=DiscordAPI.get_headers())
                if res.status_code != 200: break
                data = res.json()
                if not data: break
                guilds.extend(data)
                if len(data) < 200: break
                after = data[-1]['id']
        except: pass
        return guilds

    @staticmethod
    def get_guild(guild_id: str) -> Optional[Dict]:
        """
        Obtiene información de un servidor
        """
        if not BOT_TOKEN: return None
        res = requests.get(f"{API_ENDPOINT}/guilds/{guild_id}?with_counts=true", headers=DiscordAPI.get_headers())
        if res.status_code == 200: return res.json()
        return None
    
    @staticmethod
    def get_guild_member(guild_id: str, user_id: str) -> Optional[Dict]:
        """
        Obtiene información de un miembro de un servidor
        """
        if not BOT_TOKEN: return None
        res = requests.get(f"{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}", headers=DiscordAPI.get_headers())
        if res.status_code == 200: return res.json()
        return None
    
    @staticmethod
    def get_guild_channels(guild_id: str) -> List[Dict]:
        """
        Obtiene los canales de un servidor
        """
        if not BOT_TOKEN: return []
        res = requests.get(f"{API_ENDPOINT}/guilds/{guild_id}/channels", headers=DiscordAPI.get_headers())
        if res.status_code == 200: return res.json()
        return []

    @staticmethod
    def get_guild_roles(guild_id: str) -> List[Dict]:
        """
        Obtiene los roles de un servidor
        """
        if not BOT_TOKEN: return []
        res = requests.get(f"{API_ENDPOINT}/guilds/{guild_id}/roles", headers=DiscordAPI.get_headers())
        if res.status_code == 200: return res.json()
        return []

    @staticmethod
    def get_user(user_id: str) -> Optional[Dict]:
        """
        Obtiene información de un usuario
        """
        if not BOT_TOKEN: return None
        res = requests.get(f"{API_ENDPOINT}/users/{user_id}", headers=DiscordAPI.get_headers())
        if res.status_code == 200: return res.json()
        return None

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
        Modifica el apodo del bot en un servidor
        """
        if not BOT_TOKEN: return False
        url = f"{API_ENDPOINT}/guilds/{guild_id}/members/@me"
        
        # If nick is empty string, set it to None to reset or send empty
        # Discord API: "Requires the CHANGE_NICKNAME permission."
        payload = {}
        if nick is not None:
             payload["nick"] = nick
             
        res = requests.patch(url, json=payload, headers=DiscordAPI.get_headers())
        return res.status_code == 200

