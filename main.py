import discord
from discord.ext import commands
import asyncio
from config import BOT, PREFIX, LOG_CHANNEL, SERVER_LOG_CHANNEL
from utils.db import DBManager
import os
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

async def get_or_create_invite(guild):
    """
    Obtiene el enlace de invitación de la DB si existe y es válido.
    Si no existe o no es válido, crea uno nuevo y lo guarda en la DB.
    """
    config = await DBManager.get_guild_config(guild.id)
    
    if config and config.get('invite_url'):
        stored_invite = config.get('invite_url')
        
        try:
            invites = await guild.invites()
            for inv in invites:
                if inv.url == stored_invite:
                    return stored_invite
        except Exception as e:
            print(f"[Invite] No se pudieron listar invitaciones de {guild.name}: {e}")
    
    invite_url = None
    try:
        target_ch = guild.system_channel or next(
            (c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), 
            None
        )
        if target_ch:
            inv = await target_ch.create_invite(max_age=0, max_uses=0, reason="Bot startup invite")
            invite_url = inv.url
            
            await DBManager.update_guild_config_field(guild.id, 'invite_url', invite_url)
    except Exception as e:
        print(f"Could not create invite for {guild.name}: {e}")
    
    return invite_url

@bot.event
async def on_ready():
    """
    Se ejecuta cuando el bot está listo.
    Se encarga de enviar un mensaje al canal de logs con la información del bot y los servidores en los que está.
    """
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    # Initialize Stats (usar el número real de servidores, no un valor fijo)
    await DBManager.init_bot_stats(len(bot.guilds))

    log_channel = bot.get_channel(LOG_CHANNEL)
    if log_channel:
        guilds_data = []
        for g in bot.guilds:
            invite_url = await get_or_create_invite(g)
            invite_display = invite_url if invite_url else "No disponible"
            guilds_data.append(f"• **{g.name}** (ID: {g.id})\n  Link: {invite_display}")
            
        guilds_info = "\n".join(guilds_data) or "Ninguno"
        
        embed = discord.Embed(title="Bot Iniciado", description=f"El bot **{bot.user.name}** está listo.", color=discord.Color.green())
        if bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        embed.add_field(name=f"Servidores ({len(bot.guilds)})", value=guilds_info, inline=False)
        
        await log_channel.send(embed=embed)

@bot.event
async def on_guild_join(guild):
    """
    Se ejecuta cuando el bot es añadido a un servidor.
    Se encarga de añadir el servidor a la base de datos y enviar un mensaje al canal de serverlogs.
    """
    await DBManager.increment_servers()

    # Initialize Guild Config (Invite + Default Prefix)
    try:
        await get_or_create_invite(guild)
        await DBManager.update_guild_config_field(guild.id, 'prefix', PREFIX)
    except Exception as e:
        print(f"Error initializing guild config for {guild.name}: {e}")

    channel = bot.get_channel(SERVER_LOG_CHANNEL)
    if channel:
        embed = discord.Embed(
            title=f"{bot.user} Añadido a un servidor",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Nombre", value=guild.name, inline=True)
        embed.add_field(name="Creado el", value=guild.created_at.strftime("%d/%m/%Y %H:%M"), inline=True)
        embed.add_field(name="Owner", value=str(guild.owner), inline=True)
        embed.set_footer(text=f"ID: {guild.id}")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        elif bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
        
        await channel.send(embed=embed)

@bot.event
async def on_guild_remove(guild):
    """
    Se ejecuta cuando el bot es eliminado de un servidor.
    Se encarga de eliminar el servidor de la base de datos y enviar un mensaje al canal de serverlogs.
    """
    await DBManager.decrement_servers()
    channel = bot.get_channel(SERVER_LOG_CHANNEL)
    if channel:
        embed = discord.Embed(
            title=f"{bot.user} Eliminado de un servidor",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Nombre", value=guild.name, inline=True)
        embed.add_field(name="Creado el", value=guild.created_at.strftime("%d/%m/%Y %H:%M"), inline=True)
        embed.add_field(name="Owner", value=str(guild.owner), inline=True)
        embed.set_footer(text=f"ID: {guild.id}")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        elif bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)
            
        await channel.send(embed=embed)

async def load_extensions():
    """
    Carga todas las extensiones del bot.
    """
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

async def main():
    """
    Función principal que inicia el bot.
    """
    async with bot:
        await load_extensions()
        await bot.start(BOT)

if __name__ == "__main__":
    asyncio.run(main())