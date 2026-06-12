from cogs.tourney import DOC_URL, MAX_TOURNEY_NAME_LEN, MAX_TOURNEY_DESC_LEN
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
import requests
import uvicorn
import os
import asyncio
from typing import Optional
from datetime import datetime, timedelta, timezone


def utcnow():
    """Ahora en UTC (aware). Reemplaza a datetime.utcnow() (deprecado)."""
    return datetime.now(timezone.utc)
from utils.db import DBManager
from utils.api import DiscordAPI
from config import DISCORD_CLIENT_ID as CLIENT_ID, DISCORD_CLIENT_SECRET as CLIENT_SECRET, REDIRECT_URI, API_ENDPOINT, SESSION_SECRET as SECRET_KEY

app = FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Montar archivos estáticos
app.mount("/css", StaticFiles(directory="docLA/css"), name="css")
app.mount("/js", StaticFiles(directory="docLA/js"), name="js")
app.mount("/img", StaticFiles(directory="img"), name="img")
try:
    app.mount("/data", StaticFiles(directory="docLA/data"), name="data")
except: pass

# URL base de documentación normalizada (sin barra final) para construir enlaces sin '//'
DOC_URL_BASE = (DOC_URL or "").rstrip("/")


def render_html(path: str) -> str:
    """Lee un HTML y sustituye el placeholder ${DOC_URL} por la URL base real."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content.replace("${DOC_URL}", DOC_URL_BASE)


async def user_can_manage(guild_id: int, request: Request) -> bool:
    """
    Comprueba si el usuario de la sesión puede GESTIONAR el servidor:
    es administrador (permiso OAuth) o tiene un rol de organizador configurado.
    Reutilizable por todos los endpoints que mutan datos del servidor.
    """
    user = request.session.get("user")
    token = request.session.get("access_token")
    if not user:
        return False

    user_guilds = []
    if token:
        try:
            resp = await asyncio.to_thread(
                lambda: requests.get(
                    f"{API_ENDPOINT}/users/@me/guilds",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                ).json()
            )
            if isinstance(resp, list):
                user_guilds = resp
        except Exception:
            user_guilds = []

    target = next((g for g in user_guilds if g.get('id') == str(guild_id)), None)
    if target:
        perm_int = int(target.get('permissions', 0))
        if (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20:
            return True

    # Rol de organizador configurado en la guild
    try:
        config = await DBManager.get_or_create_guild_config(guild_id)
        admin_roles = config.get("admin_roles", [])
        if admin_roles:
            mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), user['id'])
            if mem and any(rid in admin_roles for rid in mem.get('roles', [])):
                return True
    except Exception:
        pass
    return False

# ==========================================
# RUTAS DE VISTAS (Clean URLs)
# ==========================================
@app.get("/")
async def serve_home():
    return HTMLResponse(content=render_html("docLA/index.html"))

@app.get("/sitemap.xml")
async def serve_sitemap():
    return FileResponse("docLA/sitemap.xml")

@app.get("/robots.txt")
async def serve_robots():
    return FileResponse("docLA/robots.txt")

@app.get("/docs")
async def serve_docs():
    return HTMLResponse(content=render_html("docLA/doc.html"))

@app.get("/dashboard")
async def serve_dashboard():
    return HTMLResponse(content=render_html("docLA/dashboard.html"))

@app.get("/server")
async def serve_server(guild_id: Optional[str] = None, id: Optional[str] = None):
    with open("docLA/server.html", "r", encoding="utf-8") as f:
        content = f.read()

    # Aceptar tanto ?guild_id= como ?id= (el frontend usa ?id=)
    gid = guild_id or id
    if gid:
        # Update URL for SEO/Sharing (sin doble barra)
        target_url = f"{DOC_URL_BASE}/server?guild_id={gid}"
        content = content.replace('content="${DOC_URL}/server"', f'content="{target_url}"')

    # Sustituir cualquier ${DOC_URL} restante (og:image, twitter, etc.)
    content = content.replace("${DOC_URL}", DOC_URL_BASE)
    return HTMLResponse(content=content)

@app.get("/tournament")
async def serve_tournament(tourney: Optional[str] = None, id: Optional[str] = None, guild: Optional[str] = None):
    with open("docLA/tournament.html", "r", encoding="utf-8") as f:
        content = f.read()

    # Los enlaces reales usan ?guild=...&tourney=...; mantener ?id= como alternativa
    tourney_id = tourney or id
    if tourney_id:
        # Attempt to fetch tournament details for better SEO
        try:
            t = await DBManager.get_tournament(tourney_id)
            if t:
                # Update Title
                new_title = f"{t['name']} - Detalle del Torneo"
                content = content.replace('content="Tourney Bot - Detalle del Torneo"', f'content="{new_title}"')

                # Update Description
                desc = t.get("description", "")
                if desc:
                    # Basic sanitization for meta tag
                    desc = desc.replace('"', "'").replace('\n', ' ')[:150] + "..."
                    content = content.replace('content="Visualiza brackets, equipos y resultados del torneo en tiempo real."', f'content="{desc}"')

                # Update URL (sin doble barra y con los params reales)
                target_url = f"{DOC_URL_BASE}/tournament?guild={guild or t.get('guild_id','')}&tourney={tourney_id}"
                content = content.replace('content="${DOC_URL}/tournament"', f'content="{target_url}"')
        except Exception as e:
            print(f"SSR Error tournament: {e}")

    # Sustituir cualquier ${DOC_URL} restante (og:image, twitter, etc.)
    content = content.replace("${DOC_URL}", DOC_URL_BASE)
    return HTMLResponse(content=content)

# ==========================================
# RUTAS DE AUTH
# ==========================================
@app.get("/login")
async def login(request: Request, redirect: str = None):
    # Store redirect URL in session for after callback
    if redirect:
        request.session["redirect_after_login"] = redirect
    return RedirectResponse(
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    )

@app.get("/callback")
async def callback(code: str, request: Request):
    try:
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        # Requests es síncrono, idealmente usar aiohttp, pero para este uso es aceptable
        token_response = await asyncio.to_thread(requests.post, f"{API_ENDPOINT}/oauth2/token", data=data, headers=headers, timeout=10)
        token_response.raise_for_status()
        tokens = token_response.json()

        user_response = await asyncio.to_thread(requests.get, f"{API_ENDPOINT}/users/@me", headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        }, timeout=10)
        user_response.raise_for_status()
        user_data = user_response.json()
        
        request.session["user"] = user_data
        request.session["access_token"] = tokens["access_token"]

        # Save user to DB
        await DBManager.save_user(user_data)
        
        # Check for redirect URL stored before login
        redirect_url = request.session.pop("redirect_after_login", None)
        if redirect_url:
            return RedirectResponse(url=redirect_url)
        return RedirectResponse(url="/dashboard")
    except Exception as e:
        print(f"[callback] Error de OAuth: {e}")
        return JSONResponse(status_code=400, content={"error": "No se pudo completar el inicio de sesión."})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/api/user")
async def get_user(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})
    return JSONResponse(content=user)

# ==========================================
# RUTAS DE API (DASHBOARD)
# ==========================================
@app.get("/api/guilds")
async def api_guilds(request: Request):
    user = request.session.get("user")
    token = request.session.get("access_token")
    if not user or not token:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    # 1. Obtener Guilds del Usuario (OAuth) - Fuente de permisos
    try:
        user_guilds_oauth = await asyncio.to_thread(lambda: requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}, timeout=10).json())
    except Exception as e:
        print(f"[api_guilds] Error obteniendo guilds OAuth: {e}")
        return JSONResponse(content=[])

    if not isinstance(user_guilds_oauth, list):
         return JSONResponse(content=[])

    # 2. Obtener Guilds del Bot (API)
    bot_guilds = await asyncio.to_thread(DiscordAPI.get_bot_guilds)
    bot_guild_ids = {g['id'] for g in bot_guilds}

    response_guilds = []
    
    for g_data in user_guilds_oauth:
        try:
            g_id = g_data['id']
            is_bot_in = g_id in bot_guild_ids
            
            # Check permissions from OAuth data (bits 0x8=Admin, 0x20=ManageGuild)
            perm_int = int(g_data.get('permissions', 0))
            is_admin = (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20
            
            role_label = 'Miembro'
            can_manage = False

            if is_admin:
                role_label = 'Admin'
                can_manage = True
            
            # Si el bot está dentro, podemos verificar roles de Organizador configurados
            elif is_bot_in:
                # Comprobar Configuración
                try:
                    cfg = await DBManager.get_or_create_guild_config(int(g_id))
                    admin_roles = cfg.get("admin_roles", [])
                    if admin_roles:
                        # Necesitamos los roles del usuario en ese servidor
                        mem = await asyncio.to_thread(DiscordAPI.get_guild_member, g_id, user['id'])
                        if mem:
                            curr_roles = mem.get('roles', [])
                            if any(rid in admin_roles for rid in curr_roles):
                                role_label = 'Organizador'
                                can_manage = True
                except: pass
            
            # Construir Icon URL
            icon_url = None
            if g_data.get('icon'):
                icon_url = f"https://cdn.discordapp.com/icons/{g_id}/{g_data['icon']}.png"

            response_guilds.append({
                "id": g_id,
                "name": g_data['name'],
                "icon": icon_url,
                "role_label": role_label,
                "can_manage": can_manage,
                "bot_in_guild": is_bot_in
            })
            
        except Exception as e:
            print(f"Error processing guild {g_data.get('name')}: {e}")
            continue
    
    # Sort: Admin > Organizador > Miembro > No Bot, then alphabetically
    def get_sort_key(guild):
        # Priority order
        role_priority = { 'Admin': 0, 'Organizador': 1, 'Miembro': 2 }
        
        if not guild['bot_in_guild']:
            return (3, guild['name'].lower())  # No bot servers last
        
        priority = role_priority.get(guild['role_label'], 2)
        return (priority, guild['name'].lower())
    
    response_guilds.sort(key=get_sort_key)
    
    return JSONResponse(content=response_guilds)

@app.get("/api/guild/{guild_id}")
async def get_guild_details(guild_id: int, request: Request):
    user = request.session.get("user")
    token = request.session.get("access_token")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})
    
    try:
        # 1. Verificar si el Bot está en el servidor
        guild = await asyncio.to_thread(DiscordAPI.get_guild, str(guild_id))
        if not guild: return JSONResponse(status_code=404, content={"error": "Guild not found (Bot not in guild)"})
        
        # 2. Verificar permisos del usuario (Via OAuth para Admin, via BotMember para Roles)
        # Fetch User OAuth Guilds for checking Admin (efficient enough for single view)
        user_guilds_oauth = []
        if token:
             resp_g = await asyncio.to_thread(lambda: requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}, timeout=10).json())
             if isinstance(resp_g, list):
                 user_guilds_oauth = resp_g
             else:
                 print(f"OAUTH Guilds Error: {resp_g}")
                 user_guilds_oauth = []
        
        # Encontrar la guild específica en la lista OAuth
        target_oauth_guild = next((g for g in user_guilds_oauth if g['id'] == str(guild_id)), None)
        
        is_admin = False
        if target_oauth_guild:
            perm_int = int(target_oauth_guild.get('permissions', 0))
            is_admin = (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20
        
        # Intentar obtener miembro via Bot API para verificar roles y membresia si OAuth falló
        mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), user['id'])
        
        if not target_oauth_guild and not mem:
             return JSONResponse(status_code=403, content={"error": "Forbidden / Not a member"})

        config = await DBManager.get_or_create_guild_config(guild_id)
        if config and '_id' in config: config['_id'] = str(config['_id'])
        # Map for frontend consistency
        if config: config['tourney_logs_enabled'] = config.get('tourney_logs', False)

        role_label = 'Miembro'
        can_manage = False

        if is_admin:
            role_label = 'Admin'
            can_manage = True
        else:
            # Check Roles de Organizador
            admin_roles = config.get("admin_roles", [])
            if admin_roles and mem:
                 if mem:
                     curr_roles = mem.get('roles', [])
                     if any(rid in admin_roles for rid in curr_roles):
                         role_label = 'Organizador'
                         can_manage = True

        active_tourney = await DBManager.get_active_tournament(guild_id)
        history = await DBManager.get_tournaments_history(guild_id, limit=5)
        
        # Serializar torneos
        if active_tourney:
            if '_id' in active_tourney: active_tourney['_id'] = str(active_tourney.get('_id'))
            if active_tourney.get('created_at'): active_tourney['created_at'] = active_tourney['created_at'].isoformat()
            if active_tourney.get('settings') and '_id' in active_tourney['settings']:
                 active_tourney['settings']['_id'] = str(active_tourney['settings']['_id'])
            
        history_clean = []
        for t in history:
            if '_id' in t: t['_id'] = str(t.get('_id'))
            if t.get('created_at'): t['created_at'] = t['created_at'].isoformat()
            if t.get('settings') and '_id' in t['settings']:
                 t['settings']['_id'] = str(t['settings']['_id'])
            
            # Resolve Winner Name from DB (Teams Collection)
            if t.get('winner_id') and t.get('winner_id') != "BYE_SLOT":
                try:
                    w_team = await DBManager.get_team(t['winner_id'])
                    t['winner_name'] = w_team['name'] if w_team else "Desconocido"
                except:
                    t['winner_name'] = "Error"
            else:
                 t['winner_name'] = None
            history_clean.append(t)

        # Fetch Channels for Config dropdowns
        channels_raw = await asyncio.to_thread(DiscordAPI.get_guild_channels, str(guild_id))
        
        text_channels = []
        categories_list = []
        if isinstance(channels_raw, list):
            text_channels = [{"id": c['id'], "name": c['name'], "type": str(c['type'])} for c in channels_raw if c['type'] == 0]
            categories_list = [{"id": c['id'], "name": c['name'], "type": str(c['type'])} for c in channels_raw if c['type'] == 4]
        
        # Fetch Roles for Admin Roles display
        roles_raw = await asyncio.to_thread(DiscordAPI.get_guild_roles, str(guild_id))
        roles_list = []
        if isinstance(roles_raw, list):
            roles_list = [{"id": r['id'], "name": r['name'], "color": r.get('color', 0), "position": r.get('position', 0)} for r in roles_raw if r['name'] != '@everyone']
            roles_list.sort(key=lambda x: x['position'], reverse=True)
        
        icon_url = DiscordAPI.get_icon_url(str(guild_id), guild.get('icon'))

        # Convert channel IDs in config to strings to prevent JS precision loss.
        # Solo se expone la configuración a quienes pueden gestionar el servidor.
        config_safe = None
        if config and can_manage:
            config_safe = dict(config)
            id_fields = ['category_id', 'bracket_channel_id', 'lobby_channel_id', 'bot_admin_channel_id', 'tourney_log_channel_id', 'playing_role_id']
            for field in id_fields:
                if config_safe.get(field):
                    config_safe[field] = str(config_safe[field])
            # Ensure tourney_logs_enabled is set
            config_safe['tourney_logs_enabled'] = config.get('tourney_logs_enabled', config.get('tourney_logs', False))

        return JSONResponse(content={
            "guild": {
                "id": str(guild['id']),
                "name": guild['name'],
                "icon": icon_url,
                "member_count": guild.get('approximate_member_count', 0),
                "role_label": role_label,
                "can_manage": can_manage
            },
            "config": config_safe,
            "active_tournament": active_tourney,
            "history": history_clean,
            "channels": text_channels,
            "categories": categories_list,
            "roles": roles_list
        })
    except Exception as e:
        print(f"Error in get_guild_details: {e}")
        return JSONResponse(status_code=500, content={"error": "Error interno del servidor."})

@app.get("/api/guild/{guild_id}/public")
async def get_guild_public(guild_id: int, request: Request):
    """
    Public endpoint for guild details - works with or without session.
    If logged in, shows permissions. If not, shows as member view.
    """
    user = request.session.get("user")
    token = request.session.get("access_token")
    
    try:
        # 1. Verificar si el Bot está en el servidor
        guild = await asyncio.to_thread(DiscordAPI.get_guild, str(guild_id))
        if not guild: 
            return JSONResponse(status_code=404, content={"error": "Guild not found (Bot not in guild)"})
        
        role_label = 'Miembro'
        can_manage = False
        config = None
        
        # Only check permissions if user is logged in
        if user and token:
            user_guilds_oauth = []
            resp_g = await asyncio.to_thread(lambda: requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}, timeout=10).json())
            if isinstance(resp_g, list):
                user_guilds_oauth = resp_g
            
            target_oauth_guild = next((g for g in user_guilds_oauth if g['id'] == str(guild_id)), None)
            
            is_admin = False
            if target_oauth_guild:
                perm_int = int(target_oauth_guild.get('permissions', 0))
                is_admin = (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20
            
            mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), user['id'])
            
            config = await DBManager.get_or_create_guild_config(guild_id)
            
            if is_admin:
                role_label = 'Admin'
                can_manage = True
            else:
                if not mem:
                    role_label = 'Externo'
                else:
                    # Role check for Organizer
                    admin_roles = config.get("admin_roles", [])
                    if admin_roles:
                        curr_roles = mem.get('roles', [])
                        if any(rid in admin_roles for rid in curr_roles):
                            role_label = 'Organizador'
                            can_manage = True
        
        # Get config (always needed for tournament data)
        # config already fetched above if user logged in, but ensure it is fetched if not
        if not config:
             config = await DBManager.get_or_create_guild_config(guild_id)

        if config and '_id' in config: config['_id'] = str(config['_id'])
        # Only set tourney_logs_enabled from tourney_logs if the field doesn't exist
        if config and 'tourney_logs_enabled' not in config:
            config['tourney_logs_enabled'] = config.get('tourney_logs', False)
            
        invite_url = config.get('invite_url') if config else None

        # Get tournaments
        active_tourney = await DBManager.get_active_tournament(guild_id)
        history = await DBManager.get_tournaments_history(guild_id, limit=5)
        
        # Serialize tournaments
        if active_tourney:
            if '_id' in active_tourney: active_tourney['_id'] = str(active_tourney.get('_id'))
            if active_tourney.get('created_at'): active_tourney['created_at'] = active_tourney['created_at'].isoformat()
            if active_tourney.get('settings') and '_id' in active_tourney['settings']:
                active_tourney['settings']['_id'] = str(active_tourney['settings']['_id'])
            
        history_clean = []
        for t in history:
            if '_id' in t: t['_id'] = str(t.get('_id'))
            if t.get('created_at'): t['created_at'] = t['created_at'].isoformat()
            if t.get('settings') and '_id' in t['settings']:
                t['settings']['_id'] = str(t['settings']['_id'])
            
            if t.get('winner_id') and t.get('winner_id') != "BYE_SLOT":
                try:
                    w_team = await DBManager.get_team(t['winner_id'])
                    t['winner_name'] = w_team['name'] if w_team else "Desconocido"
                except:
                    t['winner_name'] = "Error"
            else:
                t['winner_name'] = None
            history_clean.append(t)

        # Fetch Channels and Roles (only if can manage)
        text_channels = []
        categories_list = []
        roles_list = []
        
        if can_manage:
            channels_raw = await asyncio.to_thread(DiscordAPI.get_guild_channels, str(guild_id))
            if isinstance(channels_raw, list):
                text_channels = [{"id": c['id'], "name": c['name'], "type": str(c['type'])} for c in channels_raw if c['type'] == 0]
                categories_list = [{"id": c['id'], "name": c['name'], "type": str(c['type'])} for c in channels_raw if c['type'] == 4]
            
            roles_raw = await asyncio.to_thread(DiscordAPI.get_guild_roles, str(guild_id))
            if isinstance(roles_raw, list):
                roles_list = [{"id": r['id'], "name": r['name'], "color": r.get('color', 0), "position": r.get('position', 0)} for r in roles_raw if r['name'] != '@everyone']
                roles_list.sort(key=lambda x: x['position'], reverse=True)
        
        icon_url = DiscordAPI.get_icon_url(str(guild_id), guild.get('icon'))

        # Convert channel IDs in config to strings to prevent JS precision loss
        config_safe = None
        if can_manage and config:
            config_safe = dict(config)
            # Convert all channel/category IDs to strings
            id_fields = ['category_id', 'bracket_channel_id', 'lobby_channel_id', 'bot_admin_channel_id', 'tourney_log_channel_id', 'playing_role_id']
            for field in id_fields:
                if config_safe.get(field):
                    config_safe[field] = str(config_safe[field])
            # Ensure tourney_logs_enabled is properly set as boolean
            config_safe['tourney_logs_enabled'] = config.get('tourney_logs_enabled', False) == True

        # Fetch Bot Member to get current nickname
        # GET /guilds/{id}/members/@me might fail for bots, so we get ID first
        bot_user = await asyncio.to_thread(DiscordAPI.get_user, "@me")
        bot_nick = None
        if bot_user:
             bot_mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), bot_user['id'])
             if bot_mem:
                 bot_nick = bot_mem.get('nick')

        return JSONResponse(content={
            "guild": {
                "id": str(guild['id']),
                "name": guild['name'],
                "icon": icon_url,
                "member_count": guild.get('approximate_member_count', 0),
                "invite_url": invite_url,
                "bot_nickname": bot_nick
            },
            "role_label": role_label,
            "can_manage": can_manage,
            "config": config_safe,
            "active_tournament": active_tourney,
            "history": history_clean,
            "channels": text_channels,
            "categories": categories_list,
            "roles": roles_list
        })
    except Exception as e:
        print(f"Error in get_guild_public: {e}")
        return JSONResponse(status_code=500, content={"error": "Error interno del servidor."})

@app.post("/api/guild/{guild_id}/config")
async def update_config(guild_id: int, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})
    
    # Permission Check Reuse?
    # For speed, verify via OAuth Admin check logic again
    token = request.session.get("access_token")
    user_guilds = []
    if token:
         resp = await asyncio.to_thread(lambda: requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}, timeout=10).json())
         if isinstance(resp, list):
             user_guilds = resp
    
    target = next((g for g in user_guilds if g['id'] == str(guild_id)), None)
    if not target: return JSONResponse(status_code=403, content={"error": "Forbidden"})

    perm_int = int(target.get('permissions', 0))
    is_admin = (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20
    
    can_manage = is_admin
    if not can_manage:
        config = await DBManager.get_or_create_guild_config(guild_id)
        admin_roles = config.get("admin_roles", [])
        if admin_roles:
             mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), user['id'])
             if mem:
                 curr_roles = mem.get('roles', [])
                 if any(rid in admin_roles for rid in curr_roles):
                     can_manage = True

    if not can_manage:
        return JSONResponse(status_code=403, content={"error": "No tienes permisos."})

    data = await request.json()
    
    # Organizers can't edit admin_roles
    if not is_admin and "admin_roles" in data:
        del data["admin_roles"]
    
    fields_to_update = ["category_id", "bracket_channel_id", "lobby_channel_id", "bot_admin_channel_id", "prefix", "tourney_log_channel_id", "tourney_logs_enabled", "admin_roles", "playing_role_id"]
    
    for field in fields_to_update:
        if field in data:
            val = data[field]
            target_field = field
            
            # Mapping fields if necessary
            if field == "tourney_logs_enabled":
                target_field = "tourney_logs_enabled"

            if isinstance(val, str) and val.isdigit() and field != "admin_roles":
                val = int(val)
            elif val == "":
                val = None
                
            await DBManager.update_guild_config_field(guild_id, target_field, val)
            
    # Handle Bot Nickname Update
    if "bot_nickname" in data:
        new_nick = data["bot_nickname"]
        # If empty, treat as reset (pass None to method? No, method takes str or None. If user sends empty string, we want to clear it)
        if new_nick == "": new_nick = None
        await asyncio.to_thread(DiscordAPI.modify_current_member, str(guild_id), new_nick)

    return JSONResponse(content={"status": "updated"})

# ==========================================
# RUTAS DE REPORTES (BUGS & SUGERENCIAS)
# ==========================================
@app.post("/api/report/bug")
async def report_bug(request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    data = await request.json()
    description = data.get("description")
    if not description: return JSONResponse(status_code=400, content={"error": "Descripción requerida"})
    if len(description) > 1500:
        return JSONResponse(status_code=400, content={"error": "La descripción es demasiado larga (máx. 1500 caracteres)."})

    # Optional: Server context
    server_id = data.get("server_id")
    server_name = data.get("server_name")
    
    # Clean Server ID if present but empty
    if server_id == "": server_id = None
    if server_id: 
        try: server_id = int(server_id)
        except: server_id = None

    report_data = {
        "description": description,
        "user_name": f"<@{user['id']}> ({user['username']})",
        "server_id": server_id,
        "server_name": server_name,
        "source": "Web"
    }

    await DBManager.create_bug_report(report_data)
    return JSONResponse(content={"status": "sent"})

@app.post("/api/report/suggestion")
async def report_suggestion(request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    data = await request.json()
    description = data.get("description")
    if not description: return JSONResponse(status_code=400, content={"error": "Descripción requerida"})
    if len(description) > 1500:
        return JSONResponse(status_code=400, content={"error": "La descripción es demasiado larga (máx. 1500 caracteres)."})

    # Optional: Server context
    server_id = data.get("server_id")
    server_name = data.get("server_name")
    
    # Clean Server ID if present but empty
    if server_id == "": server_id = None
    if server_id: 
        try: server_id = int(server_id)
        except: server_id = None

    report_data = {
        "description": description,
        "user_name": f"<@{user['id']}> ({user['username']})",
        "server_id": server_id,
        "server_name": server_name,
        "source": "Web"
    }

    await DBManager.create_suggestion_report(report_data)
    return JSONResponse(content={"status": "sent"})

# ==========================================
# RUTAS DE ESTADO (HEALTH CHECK)
# ==========================================
@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """
    Pagina de estado del bot
    """
    return HTMLResponse(content=render_html("docLA/health.html"))


@app.get("/api/health")
async def health_check_api():
    """
    Returns the latest health status from the DB.
    """
    # 1. Get History (last 24 records)
    history = await DBManager.get_health_history(limit=24)
    
    if not history:
        return JSONResponse([])
    
    sanitized_history = []
    for item in history:
        # Convert ObjectId to str if present
        if "_id" in item:
            item["_id"] = str(item["_id"])
        
        # Convert datetime to isoformat
        if "timestamp" in item and isinstance(item["timestamp"], datetime):
            item["timestamp"] = item["timestamp"].isoformat()
        if "last_seen" in item and isinstance(item["last_seen"], datetime):
            item["last_seen"] = item["last_seen"].isoformat()
            
        sanitized_history.append(item)
        
    return JSONResponse(sanitized_history)

@app.get("/api/stats")
async def get_stats():
    """
    Returns global stats for the home page.
    """
    try:
        stats = await DBManager.get_bot_stats()
        guilds = stats.get("serversOn", 0)
        tournaments = stats.get("tournamentsDone", 0)
        return JSONResponse({"guilds": guilds, "tournaments": tournaments})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/bot/live")
async def bot_live_status():
    """
    Estado en tiempo real del bot basado en el heartbeat (latido cada 30s).
    Reemplaza la dependencia del widget de Discord y de nombres hardcodeados.
    """
    try:
        hb = await DBManager.get_last_heartbeat()
        online = False
        latency = 0
        if hb:
            last_seen = hb.get("last_seen")
            if last_seen:
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                diff = (utcnow() - last_seen).total_seconds()
                if diff <= 45:  # 30s de latido + 15s de margen
                    online = True
                    latency = hb.get("latency", 0)
        return JSONResponse({"online": online, "latency": latency})
    except Exception as e:
        print(f"[bot_live_status] Error: {e}")
        return JSONResponse({"online": False, "latency": 0})

async def perform_health_check():
    """
    Performs a single health check and saves to DB.
    """
    try:
        # Check Bot Heartbeat
        hb_data = await DBManager.get_last_heartbeat()
        
        status = "offline"
        latency = 0
        
        if hb_data:
            last_seen = hb_data.get('last_seen')
            # Asegurar aware-UTC (los docs legados podrían venir naïve)
            if last_seen and last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)

            if last_seen:
                diff = (utcnow() - last_seen).total_seconds()
                # Bot sends heartbeat every 30s. Allow up to 45s grace.
                if diff <= 45:
                    status = "online"
                    latency = hb_data.get('latency', 0)

        # Record to DB history
        await DBManager.create_health_check({
            "timestamp": utcnow(),
            "latency": latency,
            "status": status
        })
        print(f"Health Check Performed. Latency: {latency}s | Status: {status}")
    except Exception as e:
        print(f"Health Check Error: {e}")

async def health_check_loop():
    """
    Scheduled health check strictly aligned to :00.
    """
    
    # 1. Align to next hour (:00)
    now = utcnow()
    # Next hour start
    next_check_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    delay_seconds = (next_check_time - now).total_seconds()
    if delay_seconds < 0: delay_seconds = 0
    
    print(f"Health Check aligned to next hour ({next_check_time.strftime('%H:%M:%S')}). Waiting {delay_seconds:.2f}s")
    await asyncio.sleep(delay_seconds)

    # 2. Strict Loop
    while True:
        try:
            # Perform check
            await perform_health_check()
            
            # Calculate next target (always next hour :00)
            now = utcnow()
            next_check_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            
            delay_seconds = (next_check_time - now).total_seconds()
            
            if delay_seconds < 0:
                print(f"Health Check running behind schedule by {abs(delay_seconds):.2f}s")
                # If significantly behind, correct to next hour from NOW
                next_check_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                delay_seconds = (next_check_time - now).total_seconds()
            
            print(f"Next Health Check at {next_check_time.strftime('%H:%M:%S')} (in {delay_seconds:.2f}s)")
            await asyncio.sleep(delay_seconds)
            
        except asyncio.CancelledError:
            print("Health Check Loop Cancelled")
            break
        except Exception as e:
            print(f"Health Check Loop Error: {e}")
            await asyncio.sleep(60) # Prevent tight loop on error

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(health_check_loop())

# ==========================================
# RUTAS DE TORNEOS
# ==========================================
import uuid
from datetime import datetime

@app.post("/api/guild/{guild_id}/tournaments/create")
async def create_tournament(guild_id: int, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    if not await user_can_manage(guild_id, request):
        return JSONResponse(status_code=403, content={"error": "No tienes permisos para gestionar este servidor."})

    active = await DBManager.get_active_tournament(guild_id)
    if active: return JSONResponse(status_code=409, content={"error": "Ya hay un torneo activo"})

    config = await DBManager.get_or_create_guild_config(guild_id)
    if config and '_id' in config: config['_id'] = str(config['_id'])

    data = await request.json()
    name = data.get("name")
    if not name: return JSONResponse(status_code=400, content={"error": "Name required"})

    description = data.get("description", "") or ""
    if len(name) > MAX_TOURNEY_NAME_LEN:
        return JSONResponse(status_code=400, content={"error": f"El nombre no puede superar los {MAX_TOURNEY_NAME_LEN} caracteres."})
    if len(description) > MAX_TOURNEY_DESC_LEN:
        return JSONResponse(status_code=400, content={"error": f"La descripción no puede superar los {MAX_TOURNEY_DESC_LEN} caracteres."})

    try: max_teams = int(data.get("max_teams", 16))
    except: max_teams = 16

    # Validación coherente con el comando del bot: múltiplo de 2 y rango 2-64
    if max_teams < 2 or max_teams > 64 or max_teams % 2 != 0:
        return JSONResponse(status_code=400, content={"error": "El máximo de equipos debe ser un múltiplo de 2 entre 2 y 64."})

    try:
        min_members = int(data.get("min_members", 1))
        max_members = int(data.get("max_members", 5))
    except (ValueError, TypeError):
        return JSONResponse(status_code=400, content={"error": "Los miembros mínimo y máximo deben ser números enteros."})
    if min_members < 1 or max_members < 1 or min_members > max_members:
        return JSONResponse(status_code=400, content={"error": "Rango de miembros inválido (min >= 1 y min <= max)."})

    date_str = data.get("date", utcnow().strftime("%Y-%m-%d"))
    reg_start = data.get("reg_start", "00:00")
    reg_end = data.get("reg_end", "23:59")
    start_time = data.get("start_time", "18:00")
    
    full_start_date = f"{date_str} {start_time}"

    tourney_id = str(uuid.uuid4())[:8]
    
    new_tourney = {
        "id": tourney_id,
        "name": name,
        "guild_id": guild_id,
        "settings": config,
        "status": "open",
        "current_round": 0,
        "matches": [], 
        "created_at": utcnow(),
        "date": date_str,
        "registration_start_time": reg_start,
        "registration_end_time": reg_end,
        "start_time": start_time,
        "start_date": full_start_date,
        "max_teams": max_teams,
        "min_members": min_members,
        "max_members": max_members,
        "description": description,
        "winner_id": None,
        "last_bracket_url": None
    }
    
    # Handle Image URL - store null if empty
    image_url = data.get("image_url")
    # Treat empty string or whitespace as None
    if image_url and not image_url.strip():
        image_url = None
    
    new_tourney["image_url"] = image_url

    if not new_tourney["image_url"]:
        try:
            guild_data = await asyncio.to_thread(DiscordAPI.get_guild, str(guild_id))
            if guild_data and guild_data.get('icon'):
                new_tourney["image_url"] = DiscordAPI.get_icon_url(str(guild_id), guild_data['icon'])
        except Exception as e:
            print(f"Error fetching guild icon: {e}")
    
    await DBManager.create_tournament(new_tourney)
    await DBManager.increment_tournaments()
    return JSONResponse(content={"status": "created", "id": tourney_id})

@app.post("/api/guild/{guild_id}/tournament/{tournament_id}/update")
async def update_tournament(guild_id: int, tournament_id: str, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    token = request.session.get("access_token")
    user_guilds = []
    if token:
         try: 
             resp = requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}, timeout=10)
             if resp.status_code == 200:
                 user_guilds = resp.json()
         except: pass
    
    if not isinstance(user_guilds, list): user_guilds = []

    target = next((g for g in user_guilds if g.get('id') == str(guild_id)), None)
    can_manage = False

    if target:
        perm_int = int(target.get('permissions', 0))
        is_admin = (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20
        if is_admin: can_manage = True
        else:
            try:
                config = await DBManager.get_or_create_guild_config(guild_id)
                admin_roles = config.get("admin_roles", [])
                if admin_roles:
                    mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), user['id'])
                    if mem:
                         if any(rid in admin_roles for rid in mem.get('roles', [])):
                             can_manage = True
            except: pass

    if not can_manage: return JSONResponse(status_code=403, content={"error": "Forbidden"})

    data = await request.json()

    # Validación de longitudes (coherente con la creación y con el bot)
    if "name" in data and len(data["name"] or "") > MAX_TOURNEY_NAME_LEN:
        return JSONResponse(status_code=400, content={"error": f"El nombre no puede superar los {MAX_TOURNEY_NAME_LEN} caracteres."})
    if "description" in data and len(data["description"] or "") > MAX_TOURNEY_DESC_LEN:
        return JSONResponse(status_code=400, content={"error": f"La descripción no puede superar los {MAX_TOURNEY_DESC_LEN} caracteres."})

    # Fields to update
    update_data = {}
    if "name" in data: update_data["name"] = data["name"]
    if "description" in data: update_data["description"] = data["description"]
    if "max_teams" in data: update_data["max_teams"] = int(data["max_teams"])
    if "min_members" in data: update_data["min_members"] = int(data["min_members"])
    if "max_members" in data: update_data["max_members"] = int(data["max_members"])
    
    # Date/Time fields
    if "date" in data: update_data["date"] = data["date"]
    if "reg_start" in data: update_data["registration_start_time"] = data["reg_start"]
    if "reg_end" in data: update_data["registration_end_time"] = data["reg_end"]
    if "start_time" in data: update_data["start_time"] = data["start_time"]
    
    # Re-calc full start string if needed
    current_t = await DBManager.get_tournament(tournament_id)
    if not current_t:
        return JSONResponse(status_code=404, content={"error": "Torneo no encontrado"})
    d = update_data.get("date", current_t.get("date", ""))
    t = update_data.get("start_time", current_t.get("start_time", ""))
    if d and t:
        update_data["start_date"] = f"{d} {t}"
    
    # Handle image URL - store null if empty
    if "image_url" in data:
        img_url = data["image_url"]
        # Treat empty string or whitespace-only string as None
        if not img_url or not img_url.strip():
            img_url = None
        update_data["image_url"] = img_url

    # Desde la web solo se permite ABRIR/CERRAR inscripciones (open <-> pending).
    # Iniciar (active) o finalizar (finished) un torneo es exclusivo del bot, y solo
    # se permite si el torneo aún está en open/pending (no se puede reabrir uno iniciado).
    if "status" in data and data["status"] in ["pending", "open"]:
        if current_t.get("status") in ["pending", "open"]:
            update_data["status"] = data["status"]

    if not update_data: return JSONResponse(content={"status": "no_changes"})

    await DBManager.update_tournament(tournament_id, update_data)
    return JSONResponse(content={"status": "updated"})

@app.get("/api/guild/{guild_id}/tournament/{tournament_id}")
async def get_tournament_details(guild_id: int, tournament_id: str, request: Request):
    user = request.session.get("user")
    token = request.session.get("access_token")

    # Check Permissions only if logged in
    can_manage = False
    role_label = 'Miembro'
    config = None
    mem = None
    
    if user and token:
        try:
            user_guilds_oauth = []
            resp_g = await asyncio.to_thread(lambda: requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}, timeout=10).json())
            if isinstance(resp_g, list): user_guilds_oauth = resp_g
            
            target = next((g for g in user_guilds_oauth if g['id'] == str(guild_id)), None)
            
            is_admin = False
            if target:
                perm_int = int(target.get('permissions', 0))
                is_admin = (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20
                
            mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), user['id'])
            
            config = await DBManager.get_or_create_guild_config(guild_id)
            
            if is_admin:
                role_label = 'Admin'
                can_manage = True
            else:
                if not mem:
                    role_label = 'Externo'
                else:
                    admin_roles = config.get("admin_roles", [])
                    if admin_roles:
                        if any(rid in admin_roles for rid in mem.get('roles', [])):
                            role_label = 'Organizador'
                            can_manage = True
        except: pass
    # Ensure config is loaded if not already
    if not config:
        config = await DBManager.get_or_create_guild_config(guild_id)
        
    invite_url = config.get('invite_url') if config else None

    # Fetch details
    tourney = await DBManager.get_tournament(tournament_id)
    if not tourney: return JSONResponse(status_code=404, content={"error": "Tournament not found"})
    
    if '_id' in tourney: tourney['_id'] = str(tourney['_id'])
    if tourney.get('created_at'): tourney['created_at'] = tourney['created_at'].isoformat()
    
    # Winner
    if tourney.get('winner_id') and tourney.get('winner_id') != "BYE_SLOT":
        try:
            winner_team = await DBManager.get_team(tourney['winner_id'])
            tourney['winner_name'] = winner_team['name'] if winner_team else "Desconocido"
        except: tourney['winner_name'] = "Error"
    else: tourney['winner_name'] = None
    
    teams = await DBManager.get_teams(tournament_id)
    cleaned_teams = []
    
    for t in teams:
        if '_id' in t: t['_id'] = str(t['_id'])
        
        # Resolve leader info via API
        # Resolve all members
        resolved_members = []
        member_ids = t.get('members', [])
        if not member_ids and t.get('leader_id'): member_ids = [t['leader_id']] # Fallback

        for m_id in member_ids:
            m_id_str = str(m_id)
            is_leader = (str(t.get('leader_id')) == m_id_str)
            
            try:
                # Try fetch guild member first
                mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), m_id_str)
                if mem:
                    u = mem.get('user', {})
                    m_name = u.get('global_name') or u.get('username')
                    m_avatar = DiscordAPI.get_avatar_url(m_id_str, u.get('avatar'))
                else:
                    # Fallback to user fetch
                    u_api = await asyncio.to_thread(DiscordAPI.get_user, m_id_str)
                    if u_api:
                        m_name = u_api.get('global_name') or u_api.get('username')
                        m_avatar = DiscordAPI.get_avatar_url(m_id_str, u_api.get('avatar'))
                    else:
                        m_name = f"Usuario {m_id_str[-4:]}"
                        m_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"
            except:
                m_name = "Desconocido"
                m_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"

            resolved_members.append({
                "id": m_id_str,
                "name": m_name,
                "avatar": m_avatar,
                "is_leader": is_leader
            })
        
    # Sort so leader is first
        resolved_members.sort(key=lambda x: not x['is_leader'])
        t['resolved_members'] = resolved_members
        
        cleaned_teams.append(t)
    
    # Ensure guild_id is string for JS precision
    if 'guild_id' in tourney:
        tourney['guild_id'] = str(tourney['guild_id'])
    # Include is_logged_in flag for frontend
    return JSONResponse(content={
        "tournament": tourney, 
        "teams": cleaned_teams, 
        "can_manage": can_manage,
        "is_logged_in": bool(user),
        "role_label": role_label,
        "invite_url": invite_url
    })

@app.post("/api/guild/{guild_id}/tournament/{tournament_id}/delete")
async def delete_tournament(guild_id: int, tournament_id: str, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    if not await user_can_manage(guild_id, request):
        return JSONResponse(status_code=403, content={"error": "No tienes permisos para gestionar este servidor."})

    # No decrementar el contador si el torneo no existía
    existing = await DBManager.get_tournament(tournament_id)
    if not existing:
        return JSONResponse(status_code=404, content={"error": "Torneo no encontrado"})

    await DBManager.delete_tournament(tournament_id)
    await DBManager.decrement_tournaments()
    await DBManager.delete_teams_by_tournament(tournament_id)
    return JSONResponse(content={"status": "deleted"})
    
@app.post("/api/guild/{guild_id}/team/{team_id}/delete")
async def delete_team_api(guild_id: int, team_id: str, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    # Permission Check Reuse
    token = request.session.get("access_token")
    user_guilds = []
    if token:
         try: user_guilds = requests.get(f"{API_ENDPOINT}/users/@me/guilds", headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
         except: pass
    
    target = next((g for g in user_guilds if g['id'] == str(guild_id)), None)
    can_manage = False

    if target:
        perm_int = int(target.get('permissions', 0))
        is_admin = (perm_int & 0x8) == 0x8 or (perm_int & 0x20) == 0x20
        if is_admin: can_manage = True
        else:
            try:
                config = await DBManager.get_or_create_guild_config(guild_id)
                admin_roles = config.get("admin_roles", [])
                if admin_roles:
                    mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), user['id'])
                    if mem:
                         if any(rid in admin_roles for rid in mem.get('roles', [])):
                             can_manage = True
            except: pass

    if not can_manage: return JSONResponse(status_code=403, content={"error": "Forbidden"})

    team = await DBManager.get_team(team_id)
    if not team: return JSONResponse(status_code=404, content={"error": "Team not found"})
    
    tourney = await DBManager.get_tournament(team['tournament_id'])
    if not tourney: return JSONResponse(status_code=404, content={"error": "Tournament not found"})
    
    if tourney['status'] not in ['open', 'pending']:
         return JSONResponse(status_code=409, content={"error": "Can only delete teams when tournament is Open or Pending"})

    await DBManager.delete_team(team_id)
    return JSONResponse(content={"status": "deleted"})

@app.get("/api/guild/{guild_id}/blacklist")
async def get_blacklist_api(guild_id: int, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    if not await user_can_manage(guild_id, request):
        return JSONResponse(status_code=403, content={"error": "No tienes permisos para gestionar este servidor."})

    bl = await DBManager.get_blacklist(guild_id)
    
    # Resolve names from Discord API if needed, or return as is.
    resolved_bl = []
    for entry in bl:
        mem = await asyncio.to_thread(DiscordAPI.get_guild_member, str(guild_id), str(entry['user_id']))
        name = mem.get('user', {}).get('global_name') or mem.get('user', {}).get('username') if mem else f"Unknown ({entry['user_id']})"
        entry['user_name'] = name
        if '_id' in entry:
            entry['_id'] = str(entry['_id'])
        entry['user_id'] = str(entry['user_id'])
        if 'added_by' in entry:
            entry['added_by'] = str(entry['added_by'])
        entry['guild_id'] = str(entry['guild_id'])
        resolved_bl.append(entry)
        
    return JSONResponse(content={"blacklist": resolved_bl})

@app.post("/api/guild/{guild_id}/blacklist/add")
async def add_blacklist_api(guild_id: int, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    if not await user_can_manage(guild_id, request):
        return JSONResponse(status_code=403, content={"error": "No tienes permisos para gestionar este servidor."})

    data = await request.json()
    user_id = data.get("user_id")
    reason = data.get("reason", "Sin especificar")

    if not user_id: return JSONResponse(status_code=400, content={"error": "Missing user_id"})

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        return JSONResponse(status_code=400, content={"error": "user_id inválido"})

    import datetime
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    await DBManager.add_to_blacklist(guild_id, user_id_int, reason, int(user['id']), date_str)
    return JSONResponse(content={"status": "added"})

@app.post("/api/guild/{guild_id}/blacklist/remove")
async def remove_blacklist_api(guild_id: int, request: Request):
    user = request.session.get("user")
    if not user: return JSONResponse(status_code=401, content={"error": "Login required"})

    if not await user_can_manage(guild_id, request):
        return JSONResponse(status_code=403, content={"error": "No tienes permisos para gestionar este servidor."})

    try:
        data = await request.json()
        user_id = data.get("user_id")
        if not user_id: return JSONResponse(status_code=400, content={"error": "Missing user_id"})
        
        await DBManager.remove_from_blacklist(guild_id, int(user_id))
        return JSONResponse(content={"status": "removed"})
    except Exception as e:
        print(f"Error in remove_blacklist_api: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
# APP MOUNT
# APP MOUNT
# Mount specific static folder (optional usage in HTML like /static/css/...)
app.mount("/static", StaticFiles(directory="docLA", html=True), name="static")

# Mount root to serve other assets (css, js, images) from docLA folder directly
# This is a catch-all, so it must be last.
app.mount("/", StaticFiles(directory="docLA", html=True), name="static_root")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
