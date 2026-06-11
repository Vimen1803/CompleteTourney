import motor.motor_asyncio
from config import URL_BASE_1
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import datetime

# Conexión a MongoDB
# tz_aware=True: los datetimes leídos de Mongo vuelven como aware (UTC), evitando
# mezclar naïve/aware al comparar y produciendo ISO con offset para el frontend.
client = motor.motor_asyncio.AsyncIOMotorClient(URL_BASE_1, tz_aware=True)
db = client['tourney_bot']

# Helper centralizado para obtener "ahora" en UTC (aware). Reemplaza a utcnow() (deprecado).
def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)
tournaments_collection = db['tournaments']
teams_collection = db['teams']
guilds_config_collection = db['guild_config']
bugs_collection = db['bugs']
suggestions_collection = db['sugerencias']
health_collection = db['health_checks']
heartbeat_collection = db['heartbeat'] # New collection for bot liveness
users_collection = db['users'] # Collection for website users
blacklist_collection = db['blacklist'] # Collection for blacklisted users

@dataclass
class HealthCheck:
    timestamp: datetime.datetime
    latency: float
    status: str # 'online', 'maintenance', etc.
    
    def to_dict(self):
        return asdict(self)

@dataclass
class GuildConfig:
    guild_id: int
    category_id: Optional[int] = None
    bracket_channel_id: Optional[int] = None
    lobby_channel_id: Optional[int] = None
    bot_admin_channel_id: Optional[int] = None
    tourney_log_channel_id: Optional[int] = None
    # Nombre alineado con el usado realmente por bot y web (antes: tourney_logs)
    tourney_logs_enabled: Optional[bool] = False
    prefix: Optional[str] = None
    admin_roles: List[str] = None
    invite_url: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Team:
    id: str
    name: str
    members: List[int]
    leader_id: int
    tournament_id: str
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Match:
    team1_id: Optional[str]
    team2_id: Optional[str]
    winner_id: Optional[str] = None
    channel_id: Optional[int] = None
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Tournament:
    id: str
    name: str
    guild_id: int
    settings: Dict
    status: str
    current_round: int
    matches: List[List[Dict]]
    created_at: datetime.datetime
    description: str = ""
    date: str = ""
    registration_end_time: str = ""
    start_time: str = ""
    max_teams: int = 16
    min_members: int = 1
    max_members: int = 5
    image_url: Optional[str] = None
    winner_id: Optional[str] = None
    last_bracket_url: Optional[str] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class BugReport:
    description: str
    user_id: int
    user_name: str
    server_id: Optional[int]
    server_name: Optional[str]
    source: str # 'web' or 'discord'
    timestamp: datetime.datetime
    sent_to_discord: bool = False
    
    def to_dict(self):
        return asdict(self)

@dataclass
class SuggestionReport:
    description: str
    user_id: int
    user_name: str
    server_id: Optional[int]
    server_name: Optional[str]
    source: str # 'web' or 'discord'
    timestamp: datetime.datetime
    sent_to_discord: bool = False
    
    def to_dict(self):
        return asdict(self)

class DBManager:
    @staticmethod
    async def create_tournament(data: dict):
        """
        Crea un nuevo torneo
        """
        result = await tournaments_collection.insert_one(data)
        return result.inserted_id

    @staticmethod
    async def get_tournament(tournament_id: str):
        """
        Obtiene un torneo por su ID
        """
        return await tournaments_collection.find_one({"id": tournament_id})

    @staticmethod
    async def get_active_tournament(guild_id: int):
        """
        Obtiene el torneo activo de un servidor
        """
        return await tournaments_collection.find_one({"guild_id": guild_id, "status": {"$in": ["open", "active", "pending"]}})

    @staticmethod
    async def update_tournament(tournament_id: str, update_data: dict):
        """
        Actualiza un torneo
        """
        await tournaments_collection.update_one({"id": tournament_id}, {"$set": update_data})

    @staticmethod
    async def create_team(data: dict):
        """
        Crea un nuevo equipo
        """
        result = await teams_collection.insert_one(data)
        return result.inserted_id

    @staticmethod
    async def get_team(team_id: str):
        """
        Obtiene un equipo por su ID
        """
        return await teams_collection.find_one({"id": team_id})
    
    @staticmethod
    async def get_team_by_name(name: str, tournament_id: str):
        """
        Obtiene un equipo por su nombre
        """
        return await teams_collection.find_one({"name": name, "tournament_id": tournament_id})

    @staticmethod
    async def get_team_by_member(user_id: int, tournament_id: str = None):
        """
        Obtiene un equipo por el ID de uno de sus miembros
        """
        query = {"members": user_id}
        if tournament_id:
            query["tournament_id"] = tournament_id
        return await teams_collection.find_one(query)

    @staticmethod
    async def get_teams(tournament_id: str):
        """
        Obtiene todos los equipos de un torneo
        """
        cursor = teams_collection.find({"tournament_id": tournament_id})
        return await cursor.to_list(length=None)

    @staticmethod
    async def delete_team(team_id: str):
        """
        Elimina un equipo
        """
        await teams_collection.delete_one({"id": team_id})

    @staticmethod
    async def update_team(team_id: str, data: dict):
        """
        Actualiza un equipo
        """
        await teams_collection.update_one({"id": team_id}, {"$set": data})

    @staticmethod
    async def delete_tournament(tournament_id: str):
        """
        Elimina un torneo de la base de datos
        """
        await tournaments_collection.delete_one({"id": tournament_id})

    @staticmethod
    async def delete_teams_by_tournament(tournament_id: str):
        """
        Elimina todos los equipos de un torneo
        """
        await teams_collection.delete_many({"tournament_id": tournament_id})

    @staticmethod
    async def get_tournaments_history(guild_id: int, skip: int = 0, limit: int = 1):
        """
        Obtiene el historial de torneos de un servidor
        """
        cursor = tournaments_collection.find({"guild_id": guild_id}).sort("created_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
    
    @staticmethod
    async def count_tournaments(guild_id: int):
        """
        Cuenta el número de torneos de un servidor
        """
        return await tournaments_collection.count_documents({"guild_id": guild_id})

    @staticmethod
    async def get_guild_config(guild_id: int):
        """
        Obtiene la configuración de un servidor
        """
        return await guilds_config_collection.find_one({"guild_id": guild_id})

    @staticmethod
    async def get_or_create_guild_config(guild_id: int):
        """
        Obtiene la configuración de un servidor o la crea si no existe
        """
        config = await guilds_config_collection.find_one({"guild_id": guild_id})
        if not config:
            new_config = GuildConfig(guild_id=guild_id, admin_roles=[])
            await guilds_config_collection.insert_one(new_config.to_dict())
            return new_config.to_dict()
        return config

    @staticmethod
    async def update_guild_config_field(guild_id: int, field: str, value):
        """
        Actualiza un campo de la configuración de un servidor
        """
        await DBManager.get_or_create_guild_config(guild_id)
        await guilds_config_collection.update_one({"guild_id": guild_id}, {"$set": {field: value}})

    @staticmethod
    async def create_bug_report(data: dict):
        """
        Crea un reporte de bug
        """
        data['timestamp'] = utcnow()
        data['sent_to_discord'] = False
        result = await bugs_collection.insert_one(data)
        return result.inserted_id

    @staticmethod
    async def create_suggestion_report(data: dict):
        """
        Crea un reporte de sugerencia
        """
        data['timestamp'] = utcnow()
        data['sent_to_discord'] = False
        result = await suggestions_collection.insert_one(data)
        return result.inserted_id

    @staticmethod
    async def get_unsent_bugs():
        """
        Obtiene los bugs que no han sido enviados a Discord
        """
        cursor = bugs_collection.find({"sent_to_discord": False})
        return await cursor.to_list(length=None)

    @staticmethod
    async def get_unsent_suggestions():
        """
        Obtiene las sugerencias que no han sido enviadas a Discord
        """
        cursor = suggestions_collection.find({"sent_to_discord": False})
        return await cursor.to_list(length=None)

    @staticmethod
    async def mark_bug_as_sent(report_id):
        """
        Marca un bug como enviado
        """
        await bugs_collection.update_one({"_id": report_id}, {"$set": {"sent_to_discord": True}})

    @staticmethod
    async def mark_suggestion_as_sent(report_id):
        """
        Marca una sugerencia como enviada
        """
        await suggestions_collection.update_one({"_id": report_id}, {"$set": {"sent_to_discord": True}})

    @staticmethod
    async def create_health_check(data: dict):
        """
        Guarda un registro de estado del bot
        """
        # data should have timestamp, latency, status
        if 'timestamp' not in data:
            data['timestamp'] = utcnow()
        await health_collection.insert_one(data)

    @staticmethod
    async def get_health_history(limit: int = 48):
        """
        Obtiene el historial de estado
        """
        cursor = health_collection.find().sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @staticmethod
    async def update_heartbeat(latency: float = 0.0):
        """
        Updates the bot's last seen timestamp and latency.
        """
        await heartbeat_collection.update_one(
            {"_id": "bot_status"},
            {"$set": {
                "last_seen": utcnow(),
                "latency": latency
            }},
            upsert=True
        )

    @staticmethod
    async def get_last_heartbeat():
        """
        Returns the last heartbeat document.
        """
        return await heartbeat_collection.find_one({"_id": "bot_status"})

    @staticmethod
    async def get_total_tournaments():
        """
        Returns the total number of tournaments across all guilds.
        """
        return await tournaments_collection.count_documents({})

    @staticmethod
    async def get_total_guilds():
        """
        Returns the total number of guilds using the bot (based on config).
        """
        return await guilds_config_collection.count_documents({})

    @staticmethod
    async def save_user(user_data: dict):
        """
        Saves or updates a user in the database.
        """
        user_id = user_data.get("id")
        if not user_id:
            return
            
        update_data = {
            "username": user_data.get("username"),
            "discriminator": user_data.get("discriminator"),
            "last_login": utcnow()
        }
        
        await users_collection.update_one(
            {"id": user_id},
            {"$set": update_data},
            upsert=True
        )

    # ==========================
    # BOT USE STATS
    # ==========================
    bot_use_collection = db['bot_use']

    @staticmethod
    async def init_bot_stats(server_count: int):
        """
        Initializes the bot stats if they don't exist.
        Updates server count on startup to ensure accuracy.
        """
        # Check if doc exists
        stats = await DBManager.bot_use_collection.find_one({"_id": "stats"})
        if not stats:
            await DBManager.bot_use_collection.insert_one({
                "_id": "stats",
                "serversOn": server_count,
                "tournamentsDone": 0
            })
        else:
            # On startup, we trust the bot's current guild count for active servers
            await DBManager.bot_use_collection.update_one(
                {"_id": "stats"},
                {"$set": {"serversOn": server_count}}
            )

    @staticmethod
    async def increment_servers():
        """
        Increments the serversOn counter.
        """
        await DBManager.bot_use_collection.update_one(
            {"_id": "stats"},
            {"$inc": {"serversOn": 1}},
            upsert=True
        )

    @staticmethod
    async def decrement_servers():
        """
        Decrements the serversOn counter.
        """
        await DBManager.bot_use_collection.update_one(
            {"_id": "stats"},
            {"$inc": {"serversOn": -1}},
            upsert=True
        )

    @staticmethod
    async def increment_tournaments():
        """
        Increments the tournamentsDone counter.
        """
        await DBManager.bot_use_collection.update_one(
            {"_id": "stats"},
            {"$inc": {"tournamentsDone": 1}},
            upsert=True
        )

    @staticmethod
    async def decrement_tournaments():
        """
        Decrements the tournamentsDone counter.
        """
        await DBManager.bot_use_collection.update_one(
            {"_id": "stats"},
            {"$inc": {"tournamentsDone": -1}},
            upsert=True
        )

    @staticmethod
    async def get_bot_stats():
        """
        Returns the bot stats (serversOn, tournamentsDone).
        """
        stats = await DBManager.bot_use_collection.find_one({"_id": "stats"})
        if not stats:
            return {"serversOn": 0, "tournamentsDone": 0}
        # Evitar mostrar contadores negativos (los $inc -1 podrían bajar de 0)
        if stats.get("serversOn", 0) < 0:
            stats["serversOn"] = 0
        if stats.get("tournamentsDone", 0) < 0:
            stats["tournamentsDone"] = 0
        return stats

    # --- Blacklist ---

    @staticmethod
    async def add_to_blacklist(guild_id: int, user_id: int, reason: str, added_by: int, date: str):
        """
        Adds a user to the blacklist
        """
        data = {
            "guild_id": guild_id,
            "user_id": user_id,
            "reason": reason,
            "added_by": added_by,
            "date": date
        }
        await blacklist_collection.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$set": data},
            upsert=True
        )

    @staticmethod
    async def remove_from_blacklist(guild_id: int, user_id: int):
        """
        Removes a user from the blacklist
        """
        await blacklist_collection.delete_one({"guild_id": guild_id, "user_id": user_id})

    @staticmethod
    async def get_blacklisted_user(guild_id: int, user_id: int):
        """
        Gets a single blacklisted user
        """
        return await blacklist_collection.find_one({"guild_id": guild_id, "user_id": user_id})

    @staticmethod
    async def get_blacklist(guild_id: int):
        """
        Gets all blacklisted users for a guild
        """
        cursor = blacklist_collection.find({"guild_id": guild_id})
        return await cursor.to_list(length=None)
