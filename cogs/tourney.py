import discord
from discord.ext import commands
import uuid
import datetime
import random
import io
import aiohttp
from utils.db import DBManager, Tournament, Match
from utils.visual import generate_bracket_image
from config import PREFIX, BUG_CHANNEL, SUGGESTION_CHANNEL 

try:
    from config import BOT_LINK, DOC_URL
except ImportError:
    BOT_LINK = None
    DOC_URL = None

# Límites de longitud de entrada (compartidos con la web). Evitan errores de embed en Discord.
MAX_TOURNEY_NAME_LEN = 100
MAX_TOURNEY_DESC_LEN = 1000
MAX_TEAM_NAME_LEN = 50


class _ManualCtx:
    """
    Contexto mínimo que imita lo que `process_round`/`advance_round` esperan de un
    `commands.Context`, para poder reutilizarlos desde una interacción de botón
    (donde no hay un `ctx` real). Expone `guild`, `channel`, `author`, `bot` y un
    `send` defensivo (ignora errores si el canal ya no existe, p. ej. al avanzar
    de ronda se borran los canales de la ronda anterior).
    """
    def __init__(self, guild, channel, author, bot):
        self.guild = guild
        self.channel = channel
        self.author = author
        self.bot = bot

    async def send(self, *args, **kwargs):
        try:
            return await self.channel.send(*args, **kwargs)
        except Exception as e:
            print(f"[_ManualCtx] No se pudo enviar mensaje de progreso: {e}")
            return None


class Tourney(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Registra la vista persistente de reporte de resultados para que los
        # botones de los canales de enfrentamiento sigan funcionando tras un
        # reinicio del bot (los custom_id son estáticos; el match se localiza por
        # el canal donde se pulsa).
        self.bot.add_view(MatchReportView(self))

    async def cog_check(self, ctx):
        return True

    async def get_playing_role(self, guild):
        """Obtiene el rol de participante configurado en la DB para el servidor."""
        config = await DBManager.get_guild_config(guild.id)
        if not config:
            return None
        role_id = config.get('playing_role_id')
        if not role_id:
            return None
        role = guild.get_role(int(role_id))
        return role

    async def assign_participant_role(self, guild, member_ids):
        """Asigna el rol de participante a los miembros indicados."""
        role = await self.get_playing_role(guild)
        if not role:
            print(f"[Playing Role] No se encontró rol de participante para {guild.name}")
            return
        for uid in member_ids:
            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except:
                    print(f"[Playing Role] No se pudo obtener miembro {uid}")
                    continue
            if role not in member.roles:
                try:
                    await member.add_roles(role, reason="Inscrito en torneo")
                except Exception as e:
                    print(f"[Playing Role] Error asignando rol a {uid}: {e}")

    async def remove_participant_role(self, guild, member_ids):
        """Quita el rol de participante a los miembros indicados."""
        role = await self.get_playing_role(guild)
        if not role:
            return
        for uid in member_ids:
            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except:
                    continue
            if role in member.roles:
                try:
                    await member.remove_roles(role, reason="Desapuntado/eliminado del torneo")
                except Exception as e:
                    print(f"[Playing Role] Error quitando rol a {uid}: {e}")

    async def remove_participant_role_from_all(self, guild):
        """Quita el rol de participante a TODOS los miembros del servidor que lo tengan."""
        role = await self.get_playing_role(guild)
        if not role:
            return
        for member in role.members:
            try:
                await member.remove_roles(role, reason="Torneo finalizado")
            except Exception as e:
                print(f"[Playing Role] Error quitando rol a {member.id}: {e}")

    def get_embed(self, title, description, color=discord.Color.blue(), author=None, url=None):
        embed = discord.Embed(title=title, description=description, color=color, url=url)
        if author:
            embed.set_footer(text=f"Solicitado por {author.display_name}", icon_url=author.avatar.url if author.avatar else None)
        else:
            embed.set_footer(text=f"Solicitado por {self.bot.user.name}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        return embed

    async def send_log(self, guild, tourney_id: str, title: str, description: str, color: discord.Color):
        """
        Se encarga de enviar un log al canal de tourney_logs si está habilitado.
        """
        config = await DBManager.get_guild_config(guild.id)
        if not config:
            return
        
        logs_enabled = config.get("tourney_logs_enabled", False)
        log_channel_id = config.get("tourney_log_channel_id")
        
        if not logs_enabled or not log_channel_id:
            return
        
        channel = guild.get_channel(int(log_channel_id))
        if not channel:
            return
        
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=f"Servidor: {guild.name} | Server ID: {guild.id} | Torneo ID: {tourney_id}")
        embed.timestamp = discord.utils.utcnow()
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[send_log] No se pudo enviar el log al canal {log_channel_id}: {e}")

    async def is_admin(self, ctx):
        """
        Se encarga de verificar si el usuario tiene permisos de administrador o si tiene un rol permitido.
        """
        if ctx.author.guild_permissions.administrator:
            return True
        
        config = await DBManager.get_guild_config(ctx.guild.id)
        if config and 'admin_roles' in config:
            allowed_roles = config.get('admin_roles', [])
            for role in ctx.author.roles:
                if str(role.id) in allowed_roles:
                    return True
        return False
    
    async def admin_check(self, ctx):
        if not await self.is_admin(ctx):
            await ctx.send(embed=self.get_embed("Error", "No tienes permisos para ejecutar este comando.", discord.Color.red(), author=ctx.author))
            return False
        return True

    async def server_admin_check(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send(embed=self.get_embed("Error", "Solo los administradores del servidor pueden ejecutar este comando.", discord.Color.red(), author=ctx.author))
            return False
        return True

    async def channel_check(self, ctx):
        """
        Se encarga de verificar si el comando se está ejecutando en los canales permitidos.
        """
        config = await DBManager.get_guild_config(ctx.guild.id)
        if not config:
            return True
        
        lobby_channel = config.get('lobby_channel_id')
        bot_admin_channel = config.get('bot_admin_channel_id')
        
        allowed_channels = []
        if lobby_channel: allowed_channels.append(int(lobby_channel))
        if bot_admin_channel: allowed_channels.append(int(bot_admin_channel))

        if not allowed_channels:
            return True
            
        if ctx.channel.id not in allowed_channels:
            return False
        return True

    async def cog_command_error(self, ctx, error):
        """
        Se encarga de manejar los errores de los comandos.
        """
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=self.get_embed("Error de Argumentos", f"Faltan argumentos para ejecutar el comando.\nUso: `{PREFIX}{ctx.command.qualified_name} {ctx.command.signature}`", discord.Color.red(), author=ctx.author))
        elif isinstance(error, commands.BadArgument):
             await ctx.send(embed=self.get_embed("Error de Argumentos", f"Argumento inválido.\nUso: `{PREFIX}{ctx.command.qualified_name} {ctx.command.signature}`", discord.Color.red(), author=ctx.author))
        else:
            import traceback
            traceback.print_exception(type(error), error, error.__traceback__)

    @commands.group(invoke_without_command=True)
    async def tourney(self, ctx):
        """
        Se encarga de mostrar la información del bot y sus comandos.
        """
        embed = discord.Embed(
            title="Tourney Bot",
            description=f"Para más información sobre los comandos, usa `{PREFIX}tourney help` o visita la página de documentación.",
            color=discord.Color.blue()
        )
        if DOC_URL:
            embed.add_field(name="Documentación", value=f"[Haz click aquí]({DOC_URL}docs)")
        
        embed.set_footer(text=f"Solicitado por {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)

    @tourney.command(name="ping")
    async def ping(self, ctx):
        """
        Muestra la latencia del bot (Heartbeat).
        """
        hb = await DBManager.get_last_heartbeat()
        latency = 0
        status = "Offline"
        
        if hb:
            latency = hb.get("latency", 0)
            last_seen = hb.get("last_seen")
            if last_seen:
                # Asegurar aware-UTC (los docs legados podrían venir naïve)
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)
                diff = (datetime.datetime.now(datetime.timezone.utc) - last_seen).total_seconds()
                if diff < 90:
                    status = "Online"
        
        color = discord.Color.red()
        if status == "Online":
            if latency < 100:
                color = discord.Color.green()
            elif latency < 300:
                color = discord.Color.gold()
        
        embed = discord.Embed(title="🏓 Pong!", color=color)
        embed.add_field(name="Estado", value=status, inline=True)
        embed.add_field(name="Latencia (Bot)", value=f"{latency} ms", inline=True)
        await ctx.send(embed=embed)

    @tourney.command(name="link")
    async def invite_link(self, ctx):
        """
        Se encarga de mostrar el enlace de invitación del bot.
        """
        if not BOT_LINK:
            await ctx.send(embed=self.get_embed("Invitación del Bot", "No se ha configurado el enlace de invitación del bot.", author=ctx.author))
            return
        await ctx.send(embed=self.get_embed("Invitación del Bot", f"[Haz click aquí para invitarme]({BOT_LINK})", author=ctx.author))

    @tourney.command(name="doc")
    async def doc_link(self, ctx):
        """
        Se encarga de mostrar el enlace de documentación del bot.
        """
        if not DOC_URL:
            await ctx.send(embed=self.get_embed("Documentación del Bot", "No se ha configurado la documentación del bot.", author=ctx.author))
            return
        await ctx.send(embed=self.get_embed("Documentación del Bot", f"[Haz click aquí para ver la documentación]({DOC_URL}docs)", author=ctx.author))

    @tourney.command(name="suggest")
    async def suggest_cmd(self, ctx, *, desc: str):
        """
        Se encarga de enviar una sugerencia a los desarrolladores.
        """
        if not SUGGESTION_CHANNEL:
             await ctx.send(embed=self.get_embed("Error", "El canal de sugerencias no está configurado.", discord.Color.red(), author=ctx.author))
             return

        channel = self.bot.get_channel(SUGGESTION_CHANNEL)
        if not channel:
             await ctx.send(embed=self.get_embed("Error", "No se pudo encontrar el canal de sugerencias.", discord.Color.red(), author=ctx.author))
             return
        
        embed = discord.Embed(title="Nueva Sugerencia", description=desc, color=discord.Color.gold())
        embed.set_author(name=f"{ctx.author.name} ({ctx.author.id})", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        embed.set_footer(text=f"Server: {ctx.guild.name} ({ctx.guild.id})")
        embed.timestamp = discord.utils.utcnow()
        
        try:

            # await channel.send(embed=embed) # Don't send directly
            
            report_data = {
                "description": desc,
                "user_name": f"{ctx.author.mention} ({ctx.author.name})",
                "server_id": ctx.guild.id,
                "server_name": ctx.guild.name,
                "source": "Discord"
            }
            await DBManager.create_suggestion_report(report_data)

            # Entrega inmediata al canal de sugerencias (sin esperar al loop)
            reports_cog = self.bot.get_cog("Reports")
            if reports_cog:
                try:
                    await reports_cog.deliver_reports()
                except Exception as e:
                    print(f"[Reports] Error en entrega inmediata de sugerencia: {e}")

            await ctx.send(embed=self.get_embed("Sugerencia Recibida", "Tu sugerencia ha sido guardada y será revisada por los desarrolladores.", discord.Color.green(), author=ctx.author))
            
            await self.send_log(
                ctx.guild, "N/A",
                "💡 Sugerencia Registrada",
                f"**Usuario:** {ctx.author.mention}\n**Sugerencia:**\n{desc}",
                discord.Color.gold()
            )
            
        except Exception as e:
            await ctx.send(embed=self.get_embed("Error", "Ocurrió un error al guardar la sugerencia.", discord.Color.red(), author=ctx.author))
            print(f"Error saving suggestion: {e}")

    @tourney.command(name="help")
    async def tourney_help(self, ctx):
        """
        Se encarga de mostrar la ayuda del bot.
        """
        if DOC_URL:
            embed_user = self.get_embed("Ayuda - Comandos de Usuario (Página 1/2)", f"[**Documentación Completa del Bot**]({DOC_URL}docs)", author=ctx.author)
        else:
            embed_user = self.get_embed("Ayuda - Comandos de Usuario (Página 1/2)", "", author=ctx.author)
        embed_user.add_field(name=f"{PREFIX}tourney register <nombre_equipo> [@miembros...]", value="Registra un equipo en el torneo activo.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney leave", value="Abandona tu equipo actual.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney rename <nuevo_nombre>", value="Cambia el nombre de tu equipo (líder, antes de iniciar). Organizadores: `rename <id/@miembro> | <nombre>`.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney invite <@usuario>", value="Invita a un usuario a tu equipo (solo líder).", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney info [id_torneo]", value="Muestra información del torneo activo, o de uno específico por ID (incluso finalizados).", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney teams [id_torneo]", value="Muestra los equipos registrados.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney team <id_equipo>", value="Muestra info detallada de un equipo.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney historial", value="Muestra torneos pasados.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney link", value="Enlace de invitación del bot.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney doc", value="Documentación del bot.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney bug <descripción del bug>", value="Reporta un bug.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney suggest <sugerencia>", value="Envía una sugerencia a los desarrolladores.", inline=False)
        embed_user.add_field(name=f"{PREFIX}tourney ping", value="Muestra la salud del bot.", inline=False)

        embed_admin = self.get_embed("Ayuda - Comandos de Admin (Página 2/2)", "", author=ctx.author)
        embed_admin.add_field(name=f"{PREFIX}tourney create <args...>", value=f"Crea torneo. Uso: `Nombre | Desc | Fecha | IniInsc | FinInsc | IniTorneo | MaxTeams | MinMiem | MaxMiem`", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney close", value="Cierra inscripciones (Open -> Pending).", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney open", value="Abre inscripciones (Pending -> Open).", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney start [id_torneo]", value="Inicia el torneo, genera brackets y canales.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set category <id>", value="Configura Categoría del torneo.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set prefix <prefijo>", value="Cambia el prefijo del bot.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set bracket <id_canal>", value="Configura Canal de Brackets.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set lobby <id_canal>", value="Configura Canal de Lobby.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set bot_admin <id_canal>", value="Configura Canal de Admin.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set logs [id_canal]", value="Toggle logs ON/OFF. Con ID establece canal y activa.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set winner <@miembro>", value="Define el ganador mencionando a un integrante.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney settings", value="Ver configuración actual.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney roles [add/remove] <@rol>", value="Gestionar roles de admin.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney blacklist [add/remove] <@usuario>", value="Gestionar blacklist del torneo.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney kick <id_equipo / @miembro>", value="Expulsar equipo del torneo.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney delete <id_torneo>", value="Elimina un torneo de la base de datos.", inline=False)
        embed_admin.add_field(name=f"{PREFIX}tourney set playing <@rol>", value="Configura el rol de participante (se asigna al inscribirse y se menciona en brackets).", inline=False)
        
        pages = [embed_user, embed_admin]
        
        class HelpPaginator(discord.ui.View):
            """
            Se encarga de manejar la paginación de la ayuda.
            """
            def __init__(self):
                super().__init__(timeout=60)
                self.current_page = 0
            
            @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
            async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                """
                Se encarga de retroceder a la página anterior.
                """
                self.current_page = (self.current_page - 1) % len(pages)
                await interaction.response.edit_message(embed=pages[self.current_page])

            @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                """
                Se encarga de avanzar a la página siguiente.
                """
                self.current_page = (self.current_page + 1) % len(pages)
                await interaction.response.edit_message(embed=pages[self.current_page])

        await ctx.send(embed=embed_user, view=HelpPaginator())

    @tourney.command(name="create")
    async def create_tourney(self, ctx, *, args: str = ""):
        """
        Se encarga de crear un torneo.

        Formato: Nombre | Descripción | Fecha (YYYY-MM-DD) | HoraInicioInsc (HH:MM) | HoraFinInsc (HH:MM) | HoraTorneo (HH:MM) | MaxEquipos | MinMiembros | MaxMiembros
        Foto via attachment (opcional)
        """
        if not await self.admin_check(ctx): 
            return
        
        parts = [p.strip() for p in args.split('|')]
        if len(parts) < 9:
            await ctx.send(embed=self.get_embed("Error", f"Uso incorrecto. Formato:\n`{PREFIX}tourney create Nombre | Descripción | Fecha (YYYY-MM-DD) | HoraInicioInsc (HH:MM) | HoraFinInsc (HH:MM) | HoraTorneo (HH:MM) | MaxEquipos | MinMiembros | MaxMiembros`\n\nAdjunta una imagen para el banner (opcional).", discord.Color.red(), author=ctx.author))
            return

        name = parts[0]
        desc = parts[1]
        date_str = parts[2]
        reg_start = parts[3]
        reg_end = parts[4]
        tour_start = parts[5]
        
        try:
            max_teams = int(parts[6])
            min_members = int(parts[7])
            max_members = int(parts[8])
        except ValueError:
            await ctx.send(embed=self.get_embed("Error", "Los valores de MaxEquipos, MinMiembros y MaxMiembros deben ser números enteros.", discord.Color.red(), author=ctx.author))
            return

        if max_teams % 2 != 0:
            await ctx.send(embed=self.get_embed("Error", "El número máximo de equipos debe ser múltiplo de 2.", discord.Color.red(), author=ctx.author))
            return
        
        if max_teams > 64 or max_teams < 2:
            await ctx.send(embed=self.get_embed("Error", "El número máximo de equipos es 64 y el mínimo es 2.", discord.Color.red(), author=ctx.author))
            return

        # Límites de longitud (los embeds de Discord tienen tope: título 256, descripción 4096)
        if len(name) > MAX_TOURNEY_NAME_LEN:
            await ctx.send(embed=self.get_embed("Error", f"El nombre del torneo no puede superar los {MAX_TOURNEY_NAME_LEN} caracteres.", discord.Color.red(), author=ctx.author))
            return
        if len(desc) > MAX_TOURNEY_DESC_LEN:
            await ctx.send(embed=self.get_embed("Error", f"La descripción no puede superar los {MAX_TOURNEY_DESC_LEN} caracteres.", discord.Color.red(), author=ctx.author))
            return
        if min_members > max_members:
            await ctx.send(embed=self.get_embed("Error", "El mínimo de miembros no puede ser mayor que el máximo.", discord.Color.red(), author=ctx.author))
            return

        image_url = None
        if ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        else:
            # Fallback to server icon if no attachment
            if ctx.guild.icon:
                image_url = str(ctx.guild.icon.url)

        if await DBManager.get_active_tournament(ctx.guild.id):
             await ctx.send(embed=self.get_embed("Error", "Ya hay un torneo activo. Finaliza primero.", discord.Color.red(), author=ctx.author))
             return

        new_tourney = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "guild_id": ctx.guild.id,
            "settings": {},
            "status": "open",
            "current_round": 0,
            "matches": [],
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "description": desc,
            "date": date_str,
            "registration_start_time": reg_start,
            "registration_end_time": reg_end,
            "start_time": tour_start,
            "max_teams": max_teams,
            "min_members": min_members,
            "max_members": max_members,
            "image_url": image_url
        }
        
        await DBManager.create_tournament(new_tourney)
        await DBManager.increment_tournaments()
        
        await self.send_log(
            ctx.guild, new_tourney['id'],
            "🏆 Torneo Creado",
            f"**{name}**\n{desc}\n\n**Fecha:** {date_str}\n**Inscripciones:** {reg_start} - {reg_end}\n**Inicio Torneo:** {tour_start}\n**Equipos máx:** {max_teams}\n**Miembros:** {min_members}-{max_members}\n**Creado por:** {ctx.author.mention}",
            discord.Color.green()
        )
        
        ENLACE_TORNEO = f"{DOC_URL}tournament?guild={ctx.guild.id}&tourney={new_tourney['id']}"

        embed = self.get_embed("Torneo Creado", f"**{name}**\n{desc}", author=ctx.author)
        embed.add_field(name="ID", value=new_tourney['id'])
        embed.add_field(name="Fecha", value=date_str)
        embed.add_field(name="Horario", value=f"Insc: {reg_start}-{reg_end}\nTorneo: {tour_start}", inline=False)
        embed.add_field(name="Límites", value=f"Equipos: {max_teams}\nMiembros: {min_members}-{max_members}")
        # Only use valid HTTP/HTTPS URLs in embeds (Discord doesn't support data URIs)
        if image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
            embed.set_image(url=image_url)
        embed.add_field(name="", value=f"[Más Información]({ENLACE_TORNEO})", inline=False)
        embed.set_footer(text="")
        
        await ctx.send(embed=embed)

    @tourney.command(name="delete")
    async def delete_tourney(self, ctx, tourney_id: str):
        """
        Se encarga de eliminar un torneo.
        """
        if not await self.admin_check(ctx): 
            return
        
        tourney = await DBManager.get_tournament(tourney_id)
        if not tourney:
            await ctx.send(embed=self.get_embed("Error", f"No se encontró un torneo con ID `{tourney_id}`.", discord.Color.red(), author=ctx.author))
            return
        
        if tourney['guild_id'] != ctx.guild.id:
            await ctx.send(embed=self.get_embed("Error", "Este torneo no pertenece a este servidor.", discord.Color.red(), author=ctx.author))
            return
        
        tourney_name = tourney.get('name', 'Sin nombre')
        tourney_status = tourney.get('status', 'unknown')
        
        await DBManager.delete_teams_by_tournament(tourney_id)
        
        # Quitar rol de participante a todos los que lo tengan
        await self.remove_participant_role_from_all(ctx.guild)
        
        await DBManager.delete_tournament(tourney_id)
        await DBManager.decrement_tournaments()
        
        await self.send_log(
            ctx.guild, tourney_id,
            "🗑️ Torneo Eliminado",
            f"**{tourney_name}**\n\n**Estado anterior:** {tourney_status}\n**Eliminado por:** {ctx.author.mention}",
            discord.Color.orange()
        )
        
        embed = self.get_embed(
            "Torneo Eliminado",
            f"El torneo **{tourney_name}** (ID: `{tourney_id}`) ha sido eliminado correctamente.",
            discord.Color.orange(),
            author=ctx.author
        )
        embed.add_field(name="Estado anterior", value=tourney_status, inline=True)
        embed.add_field(name="Eliminado por", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)

    @tourney.command(name="settings")
    async def show_settings(self, ctx):
        """
        Se encarga de mostrar la configuración del bot en el servidor.
        """
        if not await self.admin_check(ctx): 
            return
        
        config = await DBManager.get_guild_config(ctx.guild.id)
        if not config:
             await ctx.send(embed=self.get_embed("Error", "No hay configuración de servidor guardada.", discord.Color.red(), author=ctx.author))
             return
             
        roles = config.get("admin_roles", [])
        roles_str = ", ".join([f"<@&{r}>" for r in roles]) or "Ninguno"
        logs_state = "ON" if config.get("tourney_logs_enabled", False) else "OFF"
        prefix = config.get("prefix", PREFIX)

        category_id = config.get('category_id')
        bracket_channel_id = config.get('bracket_channel_id')
        lobby_channel_id = config.get('lobby_channel_id')
        bot_admin_channel_id = config.get('bot_admin_channel_id')
        tourney_log_channel_id = config.get('tourney_log_channel_id')
        playing_role_id = config.get('playing_role_id')

        def fmt_ch(val): return f"<#{val}>" if val else "No definido"
        def fmt_val(val): return val if val else "No definido"
        def fmt_role(val): return f"<@&{val}>" if val else "No definido"
        
        desc = f"**Categoría:** {fmt_val(category_id)}\n" \
               f"**Prefijo:** `{prefix}`\n" \
               f"**Bracket Channel:** {fmt_ch(bracket_channel_id)}\n" \
               f"**Lobby Channel:** {fmt_ch(lobby_channel_id)}\n" \
               f"**Bot Admin Channel:** {fmt_ch(bot_admin_channel_id)}\n" \
               f"**Logs Channel:** {fmt_ch(tourney_log_channel_id)} ({logs_state})\n" \
               f"**Rol Playing:** {fmt_role(playing_role_id)}\n" \
               f"**Roles Admin:** {roles_str}"
               
        await ctx.send(embed=self.get_embed(f"Configuración del Servidor", desc, author=ctx.author))

    @tourney.command(name="close")
    async def tourney_close(self, ctx):
        """
        Se encarga de cerrar las inscripciones del torneo.
        """
        if not await self.admin_check(ctx): return
        
        tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not tourney:
             await ctx.send(embed=self.get_embed("Error", "No hay torneo activo.", discord.Color.red(), author=ctx.author))
             return

        if tourney['status'] != 'open':
            await ctx.send(embed=self.get_embed("Error", "Las inscripciones ya están cerradas.", discord.Color.red(), author=ctx.author))
            return
            
        await DBManager.update_tournament(tourney['id'], {"status": "pending"})
        
        await self.send_log(
            ctx.guild, tourney['id'],
            "🔒 Torneo Cerrado",
            f"**{tourney['name']}** ha pasado a estado **Pending**.\nInscripciones cerradas.",
            discord.Color.orange()
        )
        
        await ctx.send(embed=self.get_embed("Torneo Cerrado", "El estado del torneo se ha actualizado a **Pending**. Las inscripciones están ahora cerradas.", discord.Color.orange(), author=ctx.author))

    @tourney.command(name="open")
    async def tourney_open(self, ctx):
        """
        Se encarga de abrir las inscripciones del torneo.
        """
        if not await self.admin_check(ctx): return
        
        tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not tourney:
             await ctx.send(embed=self.get_embed("Error", "No hay torneo activo.", discord.Color.red(), author=ctx.author))
             return

        if tourney['status'] == 'open':
            await ctx.send(embed=self.get_embed("Error", "Las inscripciones ya están abiertas.", discord.Color.red(), author=ctx.author))
            return
        if tourney['status'] == 'active':
            await ctx.send(embed=self.get_embed("Error", "El torneo ya ha comenzado.", discord.Color.red(), author=ctx.author))
            return
        if tourney['status'] == 'finished':
            await ctx.send(embed=self.get_embed("Error", "El torneo ha finalizado.", discord.Color.red(), author=ctx.author))
            return
            
        await DBManager.update_tournament(tourney['id'], {"status": "open"})
        
        await self.send_log(
            ctx.guild, tourney['id'],
            "🔓 Torneo Abierto",
            f"**{tourney['name']}** ha pasado a estado **Open**.\nInscripciones abiertas.",
            discord.Color.green()
        )
        
        await ctx.send(embed=self.get_embed("Torneo Abierto", "Las inscripciones están ahora abiertas.", discord.Color.green(), author=ctx.author))

    @tourney.command(name="start")
    async def start_tourney(self, ctx, tourney_id: str = None):
        """
        Se encarga de iniciar el torneo.
        """
        if not await self.admin_check(ctx): return
        
        if tourney_id:
            tourney = await DBManager.get_tournament(tourney_id)
        else:
            tourney = await DBManager.get_active_tournament(ctx.guild.id)
            
        if not tourney:
             await ctx.send(embed=self.get_embed("Error", "Torneo no encontrado.", discord.Color.red(), author=ctx.author))
             return
             
        if tourney['status'] == "open":
             await ctx.send(embed=self.get_embed("Error", "Las inscripciones están abiertas.", discord.Color.red(), author=ctx.author))
             return
        if tourney['status'] == "active":
             await ctx.send(embed=self.get_embed("Error", "El torneo ya está activo.", discord.Color.red(), author=ctx.author))
             return
        if tourney['status'] == "finished":
             await ctx.send(embed=self.get_embed("Error", "El torneo ya ha finalizado.", discord.Color.red(), author=ctx.author))
             return
             
        teams = await DBManager.get_teams(tourney['id'])
        if len(teams) < 2:
             await ctx.send(embed=self.get_embed("Error", "Se necesitan al menos 2 equipos para iniciar.", discord.Color.red(), author=ctx.author))
             return

        # Avisar (sin bloquear) si no hay categoría configurada: sin ella no se crearán
        # los canales de enfrentamiento y los participantes no recibirán su sala.
        start_config = await DBManager.get_guild_config(ctx.guild.id)
        if not (start_config and start_config.get('category_id')):
            await ctx.send(embed=self.get_embed(
                "Aviso: Sin categoría configurada",
                f"No hay una **categoría** configurada para los partidos. El bracket se publicará, "
                f"pero **no se crearán canales de enfrentamiento**.\n"
                f"Configúrala con `{PREFIX}tourney set category <id>` antes de iniciar.",
                discord.Color.gold(), author=ctx.author
            ))

        capacity = tourney.get('max_teams', 16)
        num_matches = capacity // 2
        matches = [None] * num_matches

        for i in range(num_matches):
            matches[i] = {"team1_id": None, "team2_id": None, "winner_id": None, "channel_id": None}

        # --- Seeding estándar de eliminación simple ---
        # Método halving recursivo: seed 1 vs 2 solo en final,
        # seed 1 vs 3/4 solo en semis, etc.
        # Ejemplo 4 matches → seed_order = [1, 4, 2, 3]
        # Match 0: seed1 vs seed8 | Match 1: seed4 vs seed5
        # Match 2: seed2 vs seed7 | Match 3: seed3 vs seed6
        seed_order = [1]
        while len(seed_order) < num_matches:
            new_order = []
            total = len(seed_order) * 2 + 1
            for s in seed_order:
                new_order.append(s)
                new_order.append(total - s)
            seed_order = new_order

        shuffled_teams = list(teams)
        random.shuffle(shuffled_teams)

        # Asignar team1 según seed_order
        for match_idx, seed_pos in enumerate(seed_order):
            real_idx = seed_pos - 1  # seed_pos es 1-based
            if real_idx < len(shuffled_teams):
                matches[match_idx]['team1_id'] = shuffled_teams[real_idx]['id']

        # Asignar team2 como el "opuesto" del seed: seed S enfrenta seed (capacity+1-S)
        for match_idx, seed_pos in enumerate(seed_order):
            opponent_seed = capacity + 1 - seed_pos
            real_idx = opponent_seed - 1
            if real_idx < len(shuffled_teams):
                matches[match_idx]['team2_id'] = shuffled_teams[real_idx]['id']

        for i in range(num_matches):
            m = matches[i]
            if not m['team1_id']:
                m['winner_id'] = "BYE_SLOT"
            elif not m['team2_id']:
                m['winner_id'] = m['team1_id']
            else:
                m['winner_id'] = None

        tourney['status'] = "active"
        tourney['current_round'] = 1
        tourney['matches'] = [matches]
        
        await DBManager.update_tournament(tourney['id'], {
            "status": "active",
            "current_round": 1,
            "matches": tourney['matches']
        })
        
        teams_names = [t['name'] for t in teams]
        await self.send_log(
            ctx.guild, tourney['id'],
            "🚀 Torneo Iniciado",
            f"**{tourney['name']}**\n\n**Equipos:** {len(teams)} / {capacity}\n**Partidos R1:** {num_matches}\n**Equipos participantes:**\n" + "\n".join([f"• {n}" for n in teams_names]),
            discord.Color.green()
        )
        
        await ctx.send(f"Iniciando torneo **{tourney['name']}** con {len(teams)} equipos (Capacidad: {capacity} - {num_matches} Partidos)!")
        
        await self.process_round(ctx, tourney)
        
        if all(m['winner_id'] for m in matches):
             await ctx.send("¡Primera ronda resuelta automáticamente (BYEs)! Avanzando...")
             await self.advance_round(ctx, tourney)

    async def process_round(self, ctx, tourney):
        """
        Se encarga de procesar la ronda actual del torneo.
        """
        guild = ctx.guild
        round_num = tourney['current_round']
        current_round_matches = tourney['matches'][round_num - 1]
        
        config = await DBManager.get_guild_config(guild.id)
        if not config: config = {}
        
        teams_data = await DBManager.get_teams(tourney['id'])
        team_names = {t['id']: t['name'] for t in teams_data}
        
        async def fetch_image(url):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.read()
            except Exception as e:
                print(f"[Bracket] No se pudo descargar la imagen '{url}': {e}")
            return None

        server_icon_bytes = None
        if guild.icon:
            server_icon_bytes = await fetch_image(guild.icon.url)
            
        tourney_image_bytes = None
        if tourney.get('image_url'):
             tourney_image_bytes = await fetch_image(tourney['image_url'])
        
        bracket_buf = generate_bracket_image(
            tourney, 
            round_num, 
            team_names,
            server_name=guild.name,
            server_icon_bytes=server_icon_bytes,
            tourney_image_bytes=tourney_image_bytes
        )
        
        bracket_channel_id = config.get('bracket_channel_id')
        if bracket_channel_id:
            ch = guild.get_channel(bracket_channel_id)
            if ch:
                file = discord.File(bracket_buf, filename="bracket.png")
                playing_role_id = config.get('playing_role_id')
                role_mention = f" <@&{playing_role_id}>" if playing_role_id else ""
                msg = await ch.send(content=f"Ronda {round_num}{role_mention}", file=file, allowed_mentions=discord.AllowedMentions(roles=True))
                if msg.attachments:
                    await DBManager.update_tournament(tourney['id'], {"last_bracket_url": msg.attachments[0].url})

        category_id = config.get('category_id')
        category = guild.get_channel(category_id) if category_id else None
        
        if not category:
             pass

        new_matches_state = []
        
        for match in current_round_matches:
            if match['winner_id']:
                new_matches_state.append(match)
                continue
            
            t1_id = match['team1_id']
            t2_id = match['team2_id']
            if t1_id == "BYE_SLOT": t1_id = None
            if t2_id == "BYE_SLOT": t2_id = None
            
            t1 = next((t for t in teams_data if t['id'] == t1_id), None)
            t2 = next((t for t in teams_data if t['id'] == t2_id), None)
            
            if t1 and t2 and category:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False, attach_files=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, attach_files=True)
                }
                
                # Dar acceso a los roles de admin configurados en la DB
                admin_role_ids = config.get('admin_roles', [])
                for role_id_str in admin_role_ids:
                    try:
                        role = guild.get_role(int(role_id_str))
                        if role:
                            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    except (ValueError, TypeError):
                        pass

                match_members = t1['members'] + t2['members']
                for uid in match_members:
                    member = guild.get_member(uid)
                    if member:
                        overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
                
                ch_name = f"{t1['name']}-vs-{t2['name']}"
                try:
                    channel = await guild.create_text_channel(ch_name, category=category, overwrites=overwrites)
                    match['channel_id'] = channel.id
                    
                    import time
                    now = int(time.time())
                    end_time = now + 600 # 10 minutos
                    
                    t1_mentions = " ".join([f"<@{m}>" for m in t1['members']])
                    t2_mentions = " ".join([f"<@{m}>" for m in t2['members']])
                    content_mentions = f"{t1_mentions}\n{t2_mentions}"

                    desc = (
                        f"**Inicio de la Partida:** <t:{now}:T> | <t:{now}:R>\n"
                        f"**Fin de la Partida:** <t:{end_time}:T> | <t:{end_time}:R>\n\n"
                        f"**NORMAS DE LA PARTIDA**\n"
                        f"➡ Si tardas más de 10 minutos en aparecer en el momento que tengas que jugar, se te descalificará.\n"
                        f"➡ <@{t1['leader_id']}> pasará el link de la sala.\n"
                        f"➡ Para confirmar el ganador mandar una captura donde salga el jugador que ganó.\n\n"
                        f"**REPORTAR RESULTADO**\n"
                        f"➡ El **líder ganador** pulsa el botón de su equipo.\n"
                        f"➡ El **líder rival** confirma pulsando el botón del **mismo** equipo.\n"
                        f"➡ Si hay desacuerdo, un administrador lo resuelve con `{PREFIX}tourney set winner <@miembro>`."
                    )

                    embed = self.get_embed(f"Enfrentamiento: {t1['name']} vs {t2['name']}", desc, author=ctx.author)
                    report_view = MatchReportView(self, t1['name'], t2['name'])
                    await channel.send(content=content_mentions, embed=embed, view=report_view)
                    
                except Exception as e:
                    print(f"Error creating channel: {e}")
            
            new_matches_state.append(match)
            
        tourney['matches'][round_num - 1] = new_matches_state
        await DBManager.update_tournament(tourney['id'], {"matches": tourney['matches']})

    # ==========================================
    # REPORTE DE RESULTADOS POR LOS JUGADORES
    # ==========================================
    async def _find_active_match_by_channel(self, guild, channel_id):
        """
        Devuelve (tourney, round_idx, match) del enfrentamiento cuyo canal coincide
        con channel_id, o (None, None, None) si no hay torneo activo o no se encuentra.
        Los canales de match solo existen para la ronda en curso del torneo activo.
        """
        tourney = await DBManager.get_active_tournament(guild.id)
        if not tourney or tourney.get('status') != 'active':
            return None, None, None
        for r_idx, rnd in enumerate(tourney.get('matches', [])):
            for m in rnd:
                if m.get('channel_id') == channel_id:
                    return tourney, r_idx, m
        return None, None, None

    async def handle_match_report(self, interaction: discord.Interaction, slot: str):
        """
        Gestiona el reporte/confirmación de ganador desde los botones del canal del
        enfrentamiento. Un líder reclama el ganador; el líder rival confirma pulsando
        el botón del MISMO equipo. Si pulsa el otro equipo, es un conflicto y se anula.
        """
        guild = interaction.guild
        tourney, r_idx, match = await self._find_active_match_by_channel(guild, interaction.channel.id)
        if not match:
            await interaction.response.send_message("Este canal no corresponde a un enfrentamiento en curso.", ephemeral=True)
            return

        if match.get('winner_id'):
            await interaction.response.send_message("Este enfrentamiento ya tiene un ganador.", ephemeral=True)
            return

        t1 = await DBManager.get_team(match['team1_id']) if match.get('team1_id') and match['team1_id'] != "BYE_SLOT" else None
        t2 = await DBManager.get_team(match['team2_id']) if match.get('team2_id') and match['team2_id'] != "BYE_SLOT" else None

        uid = interaction.user.id
        # Solo los líderes de los dos equipos pueden reportar
        clicker_slot = None
        if t1 and t1.get('leader_id') == uid:
            clicker_slot = 'team1'
        elif t2 and t2.get('leader_id') == uid:
            clicker_slot = 'team2'
        if not clicker_slot:
            await interaction.response.send_message("Solo los **líderes** de los dos equipos pueden reportar el resultado.", ephemeral=True)
            return

        claimed_team = t1 if slot == 'team1' else t2
        if not claimed_team:
            await interaction.response.send_message("Ese equipo no es válido para este enfrentamiento.", ephemeral=True)
            return

        pending_slot = match.get('reported_winner_slot')
        pending_by = match.get('reported_by')

        # 1) No hay reporte previo → registrar la reclamación
        if not pending_slot:
            match['reported_winner_slot'] = slot
            match['reported_by'] = uid
            await DBManager.update_tournament(tourney['id'], {"matches": tourney['matches']})
            await interaction.response.send_message(
                f"📝 {interaction.user.mention} reporta que gana **{claimed_team['name']}**.\n"
                f"El **líder del equipo rival** debe pulsar el botón de **{claimed_team['name']}** para confirmar el resultado."
            )
            return

        # 2) Ya hay un reporte: el mismo reportante no puede autoconfirmarse
        if pending_by == uid:
            await interaction.response.send_message("Ya has enviado tu reporte. Espera a que el **líder rival** confirme.", ephemeral=True)
            return

        # 3) Responde el líder rival
        if slot == pending_slot:
            # Acuerdo → fijar ganador
            match['winner_id'] = claimed_team['id']
            match.pop('reported_winner_slot', None)
            match.pop('reported_by', None)
            await DBManager.update_tournament(tourney['id'], {"matches": tourney['matches']})
            try:
                await interaction.message.edit(view=None)
            except Exception:
                pass
            await interaction.response.send_message(f"✅ Resultado confirmado por ambos líderes: **{claimed_team['name']}** avanza.")

            await self.send_log(
                guild, tourney['id'],
                "✅ Resultado Reportado",
                f"**{tourney['name']}**\n\n**Ganador:** {claimed_team['name']}\n**Confirmado por:** {interaction.user.mention}",
                discord.Color.green()
            )

            # Si la ronda actual está completa, avanzar automáticamente
            if r_idx == tourney['current_round'] - 1:
                current_matches = tourney['matches'][r_idx]
                if all(m.get('winner_id') for m in current_matches):
                    config = await DBManager.get_guild_config(guild.id)
                    bracket_ch = None
                    if config and config.get('bracket_channel_id'):
                        bracket_ch = guild.get_channel(config.get('bracket_channel_id'))
                    progress_channel = bracket_ch or interaction.channel
                    manual_ctx = _ManualCtx(guild, progress_channel, interaction.user, self.bot)
                    await self.advance_round(manual_ctx, tourney)
        else:
            # Desacuerdo → anular reporte y avisar
            match.pop('reported_winner_slot', None)
            match.pop('reported_by', None)
            await DBManager.update_tournament(tourney['id'], {"matches": tourney['matches']})
            await interaction.response.send_message(
                "⚠️ **Conflicto:** cada líder reporta un ganador distinto, así que el reporte se ha anulado.\n"
                f"Poneos de acuerdo y volved a reportar, o pedid a un administrador que lo resuelva con `{PREFIX}tourney set winner <@miembro>`."
            )

    async def handle_match_cancel(self, interaction: discord.Interaction):
        """Anula un reporte pendiente. Lo puede hacer quien lo reportó o un admin."""
        guild = interaction.guild
        tourney, r_idx, match = await self._find_active_match_by_channel(guild, interaction.channel.id)
        if not match:
            await interaction.response.send_message("Este canal no corresponde a un enfrentamiento en curso.", ephemeral=True)
            return
        if not match.get('reported_winner_slot'):
            await interaction.response.send_message("No hay ningún reporte pendiente que anular.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.administrator
        if not is_admin:
            config = await DBManager.get_guild_config(guild.id)
            admin_roles = config.get('admin_roles', []) if config else []
            if admin_roles and any(str(r.id) in admin_roles for r in interaction.user.roles):
                is_admin = True

        if interaction.user.id != match.get('reported_by') and not is_admin:
            await interaction.response.send_message("Solo quien hizo el reporte o un administrador puede anularlo.", ephemeral=True)
            return

        match.pop('reported_winner_slot', None)
        match.pop('reported_by', None)
        await DBManager.update_tournament(tourney['id'], {"matches": tourney['matches']})
        await interaction.response.send_message(f"↩️ Reporte anulado por {interaction.user.mention}. Podéis volver a reportar el resultado.")

    @tourney.group(name="set", invoke_without_command=True)
    async def tourney_set(self, ctx):
        """
        Grupo de comandos para configurar el bot en el servidor.
        """
        await ctx.send_help(ctx.command)

    async def update_setting_helper(self, ctx, key, value):
        """
        Helper para actualizar la configuración del bot en el servidor.
        """
        if not await self.admin_check(ctx): return

        try:
            val_int = int(str(value).replace("<#", "").replace(">", ""))
            await DBManager.update_guild_config_field(ctx.guild.id, key, val_int)
            await ctx.send(embed=self.get_embed("Configuración Actualizada", f"**{key}** actualizado a `{val_int}` (<#{val_int}>)", author=ctx.author))
        except ValueError:
            await ctx.send(embed=self.get_embed("Error", "Valor inválido. Debe ser un ID o mención de canal.", discord.Color.red(), author=ctx.author))

    @tourney_set.command(name="category")
    async def set_category(self, ctx, category_id: str):
        """
        Establece la categoría donde se crearán los canales de los partidos.
        """
        await self.update_setting_helper(ctx, "category_id", category_id)

    @tourney_set.command(name="bracket")
    async def set_bracket(self, ctx, channel_id: str):
        """
        Establece el canal donde se publicará el bracket del torneo.
        """
        await self.update_setting_helper(ctx, "bracket_channel_id", channel_id)

    @tourney_set.command(name="lobby")
    async def set_lobby(self, ctx, channel_id: str):
        """
        Establece el canal donde se permitirá el registro de equipos.
        """
        await self.update_setting_helper(ctx, "lobby_channel_id", channel_id)

    @tourney_set.command(name="bot_admin")
    async def set_bot_admin(self, ctx, channel_id: str):
        """
        Establece el canal donde se realizarán las acciones administrativas del bot.
        """
        await self.update_setting_helper(ctx, "bot_admin_channel_id", channel_id)

    @tourney_set.command(name="playing")
    async def set_playing(self, ctx, role: discord.Role):
        """
        Establece el rol de participante que se asigna al inscribirse en un torneo.
        """
        if not await self.admin_check(ctx): return
        
        await DBManager.update_guild_config_field(ctx.guild.id, "playing_role_id", role.id)
        await ctx.send(embed=self.get_embed("Configuración Actualizada", f"**Rol Playing** actualizado a {role.mention}", author=ctx.author))

    @tourney_set.command(name="logs")
    async def set_logs(self, ctx, channel_id: str = None):
        """
        Establece o activa el canal donde se enviarán los logs del torneo.
        """
        if not await self.admin_check(ctx): return
        
        config = await DBManager.get_or_create_guild_config(ctx.guild.id)
        logs_enabled = config.get("tourney_logs_enabled", False)
        
        if channel_id:
            try:
                val_int = int(str(channel_id).replace("<#", "").replace(">", ""))
                await DBManager.update_guild_config_field(ctx.guild.id, "tourney_log_channel_id", val_int)
                await DBManager.update_guild_config_field(ctx.guild.id, "tourney_logs_enabled", True)
                await ctx.send(embed=self.get_embed("Logs Activados", f"Canal de logs establecido a <#{val_int}>.\nEstado: **ON**", author=ctx.author))
            except ValueError:
                await ctx.send(embed=self.get_embed("Error", "ID de canal inválido.", discord.Color.red(), author=ctx.author))
        else:
            new_state = not logs_enabled
            
            if new_state:
                if not config.get('tourney_log_channel_id'):
                     await ctx.send(embed=self.get_embed("Error", "No se puede activar los logs sin configurar primero un canal de logs.\nUsa `,tourney set logs <#canal>`.", discord.Color.red(), author=ctx.author))
                     return
            
            await DBManager.update_guild_config_field(ctx.guild.id, "tourney_logs_enabled", new_state)
            state_str = "ON" if new_state else "OFF"
            await ctx.send(embed=self.get_embed("Logs Toggle", f"Logs de torneo: **{state_str}**", author=ctx.author))

    @tourney_set.command(name="prefix")
    async def set_prefix(self, ctx, new_prefix: str):
        if not await self.admin_check(ctx): return
        
        if len(new_prefix) > 5:
             await ctx.send(embed=self.get_embed("Error", "El prefijo no puede tener más de 5 caracteres.", discord.Color.red(), author=ctx.author))
             return
             
        await DBManager.update_guild_config_field(ctx.guild.id, "prefix", new_prefix)
        await ctx.send(embed=self.get_embed("Prefijo Actualizado", f"El prefijo del bot ha sido cambiado a `{new_prefix}`", author=ctx.author))

    @tourney_set.command(name="winner")
    async def set_winner_cmd(self, ctx, member: discord.Member):
        if not await self.admin_check(ctx): return
        
        tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not tourney or tourney['status'] != "active":
             await ctx.send(embed=self.get_embed("Error", "No hay torneo activo.", discord.Color.red(), author=ctx.author))
             return
             
        team_id = None
        user_team = await DBManager.get_team_by_member(member.id, tourney['id'])
        if user_team:
            team_id = user_team['id']
        else:
            await ctx.send(embed=self.get_embed("Error", f"El usuario {member.mention} no pertenece a ningún equipo en este torneo.", discord.Color.red(), author=ctx.author))
            return

        round_idx = tourney['current_round'] - 1
        current_matches = tourney['matches'][round_idx]
        
        found_match = None
        for match in current_matches:
            if match['team1_id'] == team_id or match['team2_id'] == team_id:
                found_match = match
                break
                
        if not found_match:
             await ctx.send(embed=self.get_embed("Error", "Equipo no encontrado en la ronda actual.", discord.Color.red(), author=ctx.author))
             return
             
        if found_match['winner_id']:
             await ctx.send(embed=self.get_embed("Error", "Este enfrentamiento ya tiene ganador.", discord.Color.red(), author=ctx.author))
             return
             
        found_match['winner_id'] = team_id
        
        if found_match['channel_id']:
            ch = ctx.guild.get_channel(found_match['channel_id'])
            if ch:
                await ch.send(embed=self.get_embed("Ganador Establecido", f"El equipo **{user_team['name']}** avanza. (ID: {team_id})", author=ctx.author))
                pass 

        await DBManager.update_tournament(tourney['id'], {"matches": tourney['matches']})
        await ctx.send(embed=self.get_embed("Ganador Establecido", f"El equipo **{user_team['name']}** avanza.", author=ctx.author))
        
        if all(m['winner_id'] for m in current_matches):
            await self.advance_round(ctx, tourney)

    async def advance_round(self, ctx, tourney):
        current_matches = tourney['matches'][tourney['current_round'] - 1]
        winners = [m['winner_id'] for m in current_matches]
        
        if len(winners) == 1:
            winner_team = await DBManager.get_team(winners[0])
            
            if winners[0] == "BYE_SLOT":
                 await ctx.send(embed=self.get_embed("Torneo Finalizado", "El torneo ha finalizado sin ganador real (Rama vacía).", author=ctx.author))
                 tourney['status'] = "finished"
                 await DBManager.update_tournament(tourney['id'], {"status": "finished"})
                 return

            server_name = ctx.guild.name
            
            config = await DBManager.get_guild_config(ctx.guild.id)
            bracket_channel_id = config.get('bracket_channel_id') if config else None
            
            target_channel = ctx.channel
            if bracket_channel_id:
                bc = ctx.guild.get_channel(bracket_channel_id)
                if bc: target_channel = bc

            teams_data = await DBManager.get_teams(tourney['id'])
            team_names = {t['id']: t['name'] for t in teams_data}
            
            async def fetch_image(url):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                return await resp.read()
                except:
                    pass
                return None

            server_icon_bytes = None
            if ctx.guild.icon:
                server_icon_bytes = await fetch_image(ctx.guild.icon.url)
                
            tourney_image_bytes = None
            if tourney.get('image'):
                 tourney_image_bytes = await fetch_image(tourney['image'])
            
            tourney['winner_id'] = winner_team['id']
            
            final_bracket_buf = generate_bracket_image(
                tourney, 
                tourney['current_round'], 
                team_names,
                server_name=ctx.guild.name,
                server_icon_bytes=server_icon_bytes,
                tourney_image_bytes=tourney_image_bytes
            )
            
            if final_bracket_buf:
                file = discord.File(final_bracket_buf, filename="final_bracket.png")
                msg = await target_channel.send(content=f"", file=file)
                if msg.attachments:
                    await DBManager.update_tournament(tourney['id'], {"last_bracket_url": msg.attachments[0].url})

            if 'matches' in tourney:
                for round_matches in tourney['matches']:
                    for m in round_matches:
                        if m.get('channel_id'):
                            try:
                                channel = ctx.guild.get_channel(m['channel_id'])
                                if channel:
                                    await channel.delete(reason="Torneo finalizado")
                            except Exception as e:
                                print(f"Error deleting channel {m['channel_id']}: {e}")
            
            tourney['status'] = "finished"
            tourney['winner_id'] = winner_team['id']
            await DBManager.update_tournament(tourney['id'], {"status": "finished", "winner_id": winner_team['id']})
            
            # Quitar rol de participante a todos los usuarios que lo tengan
            await self.remove_participant_role_from_all(ctx.guild)
            ENLACE_TORNEO = f"{DOC_URL}tournament?guild={ctx.guild.id}&tourney={tourney['id']}"
            
            embed = discord.Embed(
                title="¡TORNEO FINALIZADO!",
                url=ENLACE_TORNEO,
                description=f"**{tourney.get('name', 'Torneo')}**\n\n{tourney.get('description', '')}",
                color=discord.Color.gold()
            )
            
            thumbnail_url = tourney.get('image_url')
            # Validate URL before using in embed
            if thumbnail_url and not (thumbnail_url.startswith("http://") or thumbnail_url.startswith("https://")):
                thumbnail_url = None  # Invalid URL (probably Base64), use fallback
            if not thumbnail_url and ctx.guild.icon:
                thumbnail_url = ctx.guild.icon.url
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            
            embed.add_field(name="Fecha", value=tourney.get('start_date', 'N/A'), inline=True)
            embed.add_field(name="Equipos", value=str(len(teams_data)), inline=True)
            embed.add_field(name="Rondas", value=str(tourney.get('current_round', 1)), inline=True)
            
            embed.add_field(name="EQUIPO CAMPEÓN", value=f"**{winner_team['name']}**", inline=False)
            
            members_mentions = [f"<@{uid}>" for uid in winner_team.get('members', [])]
            leader_id = winner_team.get('leader_id')
            members_str = "\n".join(members_mentions) if members_mentions else "Sin miembros"
            embed.add_field(name="LÍDER", value=f"<@{leader_id}>" if leader_id else "N/A", inline=True)
            embed.add_field(name="MIEMBROS", value=members_str, inline=True)
            
            embed.set_footer(
                text=f"{ctx.guild.name}",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
            
            await self.send_log(
                ctx.guild, tourney['id'],
                "🏆 Torneo Finalizado",
                f"**{tourney['name']}**\n\n**Campeón:** {winner_team['name']}\n**Líder:** <@{leader_id}>\n**Rondas jugadas:** {tourney.get('current_round', 1)}\n**Total equipos:** {len(teams_data)}",
                discord.Color.green()
            )
            
            await target_channel.send(embed=embed)
            
        else:
            # Borrar los canales de enfrentamiento de la ronda que acaba de terminar
            prev_round_matches = tourney['matches'][tourney['current_round'] - 1]
            for m in prev_round_matches:
                if m.get('channel_id'):
                    try:
                        channel = ctx.guild.get_channel(m['channel_id'])
                        if channel:
                            await channel.delete(reason=f"Ronda {tourney['current_round']} finalizada")
                    except Exception as e:
                        print(f"Error deleting channel {m['channel_id']}: {e}")

            tourney['current_round'] += 1
            matches = []
            for i in range(0, len(winners), 2):
                if i + 1 < len(winners):
                     w1 = winners[i]
                     w2 = winners[i+1]
                     
                     new_match = {"team1_id": w1, "team2_id": w2, "winner_id": None, "channel_id": None}
                     
                     if w1 == "BYE_SLOT" and w2 == "BYE_SLOT":
                         new_match["winner_id"] = "BYE_SLOT"
                     elif w1 != "BYE_SLOT" and w2 == "BYE_SLOT":
                         new_match["winner_id"] = w1
                     elif w1 == "BYE_SLOT" and w2 != "BYE_SLOT":
                         new_match["winner_id"] = w2
                         
                     matches.append(new_match)
                else:
                     pass
            
            tourney['matches'].append(matches)
            await DBManager.update_tournament(tourney['id'], {
                "current_round": tourney['current_round'],
                "matches": tourney['matches']
            })
            
            prev_round = tourney['current_round'] - 1
            prev_matches = tourney['matches'][prev_round - 1]
            team_names = await DBManager.get_teams(tourney['id'])
            team_map = {t['id']: t['name'] for t in team_names}
            
            summary_lines = []
            for m in prev_matches:
                t1_name = team_map.get(m['team1_id'], 'BYE') if m['team1_id'] != "BYE_SLOT" else "BYE"
                t2_name = team_map.get(m['team2_id'], 'BYE') if m['team2_id'] != "BYE_SLOT" else "BYE"
                winner_name = team_map.get(m['winner_id'], 'BYE') if m['winner_id'] != "BYE_SLOT" else "BYE"
                summary_lines.append(f"**{t1_name}** vs **{t2_name}** → 🏆 {winner_name}")
            
            await self.send_log(
                ctx.guild, tourney['id'],
                f"📊 Resumen Ronda {prev_round}",
                f"**{tourney['name']}**\n\n" + "\n".join(summary_lines) + f"\n\n*Avanzando a Ronda {tourney['current_round']}...*",
                discord.Color.purple()
            )
            
            await ctx.send(f"¡Ronda {tourney['current_round'] - 1} finalizada! Iniciando Ronda {tourney['current_round']}...")
            await self.process_round(ctx, tourney)

            new_round_matches = tourney['matches'][-1]
            if all(m['winner_id'] for m in new_round_matches):
                await ctx.send(f"¡Ronda {tourney['current_round']} resuelta automáticamente! Avanzando...")
                await self.advance_round(ctx, tourney)


    @tourney.group(name="roles")
    async def roles_group(self, ctx):
        """
        Grupo de comandos para roles
        """
        if ctx.invoked_subcommand is None:
            await self.show_roles(ctx)

    async def show_roles(self, ctx):
        """
        Muestra los roles permitidos
        """
        if not await self.server_admin_check(ctx): return
        
        config = await DBManager.get_guild_config(ctx.guild.id)
        if not config:
            await ctx.send("No hay configuración.")
            return

        roles = config.get("admin_roles", [])
        roles_mentions = [f"<@&{r}>" for r in roles]
        await ctx.send(embed=self.get_embed("Roles Permitidos", "\n".join(roles_mentions) if roles_mentions else "Ninguno", author=ctx.author))

    @roles_group.command(name="add")
    async def add_role(self, ctx, role: discord.Role):
        """
        Añade un rol a los permitidos
        """
        if not await self.server_admin_check(ctx): return
        
        config = await DBManager.get_or_create_guild_config(ctx.guild.id)
        current_roles = config.get("admin_roles", [])
        
        if str(role.id) not in current_roles:
            current_roles.append(str(role.id))
            await DBManager.update_guild_config_field(ctx.guild.id, "admin_roles", current_roles)
            await ctx.send(embed=self.get_embed("Rol Añadido", f"Se ha añadido {role.mention} a los permitidos.", author=ctx.author))
        else:
            await ctx.send(embed=self.get_embed("Error", "Ese rol ya está en la lista.", author=ctx.author))

    @roles_group.command(name="remove")
    async def remove_role(self, ctx, role: discord.Role):
        """
        Elimina un rol de los permitidos
        """ 
        if not await self.server_admin_check(ctx): return
        
        config = await DBManager.get_or_create_guild_config(ctx.guild.id)
        current_roles = config.get("admin_roles", [])
        
        if str(role.id) in current_roles:
            current_roles.remove(str(role.id))
            await DBManager.update_guild_config_field(ctx.guild.id, "admin_roles", current_roles)
            await ctx.send(embed=self.get_embed("Rol Eliminado", f"Se ha eliminado {role.mention} de los permitidos.", author=ctx.author))
        else:
            await ctx.send(embed=self.get_embed("Error", "Ese rol no estaba en la lista.", author=ctx.author))

    @tourney.group(name="blacklist", aliases=["bl"])
    async def blacklist_group(self, ctx):
        """
        Gestiona la blacklist de jugadores del torneo
        """
        if ctx.invoked_subcommand is None:
            await self.show_blacklist(ctx)

    async def show_blacklist(self, ctx):
        if not await self.admin_check(ctx): return
        
        bl_users = await DBManager.get_blacklist(ctx.guild.id)
        if not bl_users:
            await ctx.send(embed=self.get_embed("Blacklist", "La blacklist está vacía.", author=ctx.author))
            return
            
        desc = ""
        for idx, u in enumerate(bl_users):
            desc += f"**{idx+1}.** <@{u['user_id']}> - {u['reason']}\n"
            
        await ctx.send(embed=self.get_embed("Jugadores en Blacklist", desc, discord.Color.orange(), author=ctx.author))

    @blacklist_group.command(name="add")
    async def blacklist_add(self, ctx, member: discord.Member, *, reason: str = "Sin especificar"):
        """
        Añade un usuario a la blacklist
        """
        if not await self.admin_check(ctx): return
        
        if member.id == ctx.author.id:
            await ctx.send(embed=self.get_embed("Error", "No puedes meterte a ti mismo en la blacklist.", discord.Color.red(), author=ctx.author))
            return
            
        import datetime
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        await DBManager.add_to_blacklist(ctx.guild.id, member.id, reason, ctx.author.id, date_str)
        await ctx.send(embed=self.get_embed("Blacklist Actualizada", f"Se ha añadido a {member.mention} a la blacklist.\n**Motivo:** {reason}", discord.Color.green(), author=ctx.author))

    @blacklist_group.command(name="remove")
    async def blacklist_remove(self, ctx, member: discord.Member):
        """
        Elimina un usuario de la blacklist
        """
        if not await self.admin_check(ctx): return
        
        entry = await DBManager.get_blacklisted_user(ctx.guild.id, member.id)
        if not entry:
            await ctx.send(embed=self.get_embed("Error", "Este usuario no está en la blacklist.", discord.Color.red(), author=ctx.author))
            return
            
        await DBManager.remove_from_blacklist(ctx.guild.id, member.id)
        await ctx.send(embed=self.get_embed("Blacklist Actualizada", f"Se ha eliminado a {member.mention} de la blacklist.", discord.Color.green(), author=ctx.author))

    @tourney.command(name="info")
    async def tourney_info(self, ctx, tourney_id: str = None):
        """
        Muestra información del torneo
        """ 
        if not await self.channel_check(ctx): return

        if tourney_id:
            tourney = await DBManager.get_tournament(tourney_id)
        else:
            tourney = await DBManager.get_active_tournament(ctx.guild.id)
            
        if not tourney:
            await ctx.send(embed=self.get_embed("Error", "No se encontró torneo.", author=ctx.author, color=discord.Color.red()))
            return

        ENLACE_TORNEO = f"{DOC_URL}tournament?guild={ctx.guild.id}&tourney={tourney['id']}"
        embed = self.get_embed(f"Info Torneo: {tourney['name']}", tourney.get('description', ''), author=ctx.author, url=ENLACE_TORNEO)
        embed.add_field(name="ID", value=tourney['id'], inline=True)
        embed.add_field(name="Estado", value=tourney['status'], inline=True)
        embed.add_field(name="Ronda Actual", value=str(tourney.get('current_round', 0)), inline=True)
        
        if 'date' in tourney:
             embed.add_field(name="Fecha Evento", value=tourney['date'], inline=True)
             embed.add_field(name="Inscripciones", value=f"{tourney.get('registration_start_time','?')} - {tourney.get('registration_end_time','?')}", inline=True)
             embed.add_field(name="Inicio Torneo", value=tourney.get('start_time','?'), inline=True)
        else:
             embed.add_field(name="Inicio Programado", value=tourney.get('start_date', 'N/A'), inline=False)
        
        teams = await DBManager.get_teams(tourney['id'])
        max_teams = tourney.get('max_teams', 'âˆž')
        embed.add_field(name="Equipos", value=f"{len(teams)} / {max_teams}", inline=True)
        
        min_m = tourney.get('min_members', 1)
        max_m = tourney.get('max_members', 5)
        embed.add_field(name="Miembros por Equipo", value=f"{min_m} - {max_m}", inline=True)

        # Only use valid HTTP/HTTPS URLs in embeds
        if tourney.get("image_url") and (tourney["image_url"].startswith("http://") or tourney["image_url"].startswith("https://")):
            embed.set_image(url=tourney["image_url"])
        elif ctx.guild.icon:
            # Fallback to server icon for Base64 or invalid URLs
            embed.set_image(url=ctx.guild.icon.url)
            
        await ctx.send(embed=embed)
        
    @tourney.command(name="historial")
    async def tourney_history(self, ctx):
        """
        Muestra el historial de torneos
        """ 
        if not await self.channel_check(ctx): return
        
        async def get_history_page(page_num):
             items_per_page = 1
             skip = page_num * items_per_page
             history = await DBManager.get_tournaments_history(ctx.guild.id, skip=skip, limit=items_per_page)
             total = await DBManager.count_tournaments(ctx.guild.id)
             return history, total, items_per_page
             
        data, total, per_page = await get_history_page(0)
        if not data:
            await ctx.send("No hay historial.")
            return

        if not data:
            await ctx.send("No hay historial.")
            return

        async def build_history_embed(t, page, total):
            desc = t.get('description', '')
            embed = self.get_embed(f"Historial {page}/{total}: {t['name']}", desc, author=ctx.author)
            
            embed.add_field(name="ID", value=t['id'], inline=True)
            embed.add_field(name="Estado", value=t['status'], inline=True)
            embed.add_field(name="Fecha Inicio", value=t.get('start_date', 'N/A'), inline=True)
            
            if t.get('winner_id'):
                winner_team = await DBManager.get_team(t['winner_id'])
                w_name = winner_team['name'] if winner_team else "Desconocido"
                
                members_str = ""
                if winner_team:
                    members_str = " - ".join([f"<@{uid}>" for uid in winner_team['members']])
                
                embed.add_field(name="Ganador", value=f"**{w_name}** - {members_str}", inline=False)
            
            teams_count = await DBManager.get_teams(t['id'])
            embed.add_field(name="Equipos", value=str(len(teams_count)), inline=True)
            
            # Only use valid HTTP/HTTPS URLs in embeds
            if t.get('image_url') and (t['image_url'].startswith('http://') or t['image_url'].startswith('https://')):
                embed.set_image(url=t['image_url'])
            return embed

        embed = await build_history_embed(data[0], 1, total)

        class HistoryPaginator(discord.ui.View):
            def __init__(self, cog, total_pages):
                super().__init__(timeout=60)
                self.cog = cog
                self.current_page = 0
                self.total_pages = total_pages

            async def update_embed(self, interaction):
                data, _, _ = await get_history_page(self.current_page)
                if not data: return
                t = data[0]
                embed = await build_history_embed(t, self.current_page + 1, self.total_pages)
                await interaction.response.edit_message(embed=embed)

            @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
            async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = (self.current_page - 1) % self.total_pages
                await self.update_embed(interaction)

            @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = (self.current_page + 1) % self.total_pages
                await self.update_embed(interaction)
                
        await ctx.send(embed=embed, view=HistoryPaginator(self, total))

    @tourney.command(name="register")
    async def register_team(self, ctx, name: str, *members: discord.Member):
        """
        Registra un equipo en el torneo
        """ 
        active_tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not active_tourney:
             await ctx.send(embed=self.get_embed("Error", "No hay ningún torneo activo en este servidor para registrarse.", discord.Color.red(), author=ctx.author))
             return
        
        tourney_id = active_tourney['id']

        if name.startswith("<@") and name.endswith(">"):
             await ctx.send(embed=self.get_embed("Error de Formato", f"Parece que has introducido una mención como nombre de equipo.\nUso correcto: `{PREFIX}tourney register <NombreEquipo> <@Miembros...>`", discord.Color.red(), author=ctx.author))
             return

        if len(name) > MAX_TEAM_NAME_LEN:
             await ctx.send(embed=self.get_embed("Error", f"El nombre del equipo no puede superar los {MAX_TEAM_NAME_LEN} caracteres.", discord.Color.red(), author=ctx.author))
             return

        if active_tourney['status'] != "open":
             await ctx.send(embed=self.get_embed("Error", "El torneo no está abierto para registros.", discord.Color.red(), author=ctx.author))
             return
             
        if await DBManager.get_team_by_name(name, tourney_id):
             await ctx.send(embed=self.get_embed("Error", "Ya existe un equipo con ese nombre.", discord.Color.red(), author=ctx.author))
             return

        all_members = list(set([ctx.author] + list(members)))
        
        for member in all_members:
            bl_entry = await DBManager.get_blacklisted_user(ctx.guild.id, member.id)
            if bl_entry:
                await ctx.send(embed=self.get_embed("Blacklist", f"El usuario {member.mention} está en la blacklist y no puede participar.\n**Motivo:** {bl_entry.get('reason', 'Sin especificar')}", discord.Color.red(), author=ctx.author))
                return
                
            existing_team = await DBManager.get_team_by_member(member.id, active_tourney['id'])
            if existing_team:
                await ctx.send(embed=self.get_embed("Error", f"El usuario {member.mention} ya pertenece al equipo **{existing_team['name']}**.\nNo puede unirse a otro equipo.", discord.Color.red()))
                return
        
        min_m = active_tourney.get('min_members', 1)
        max_m = active_tourney.get('max_members', 5)
        
        if not (min_m <= len(all_members) <= max_m):
             await ctx.send(embed=self.get_embed("Error", f"El equipo debe tener entre {min_m} y {max_m} miembros (incluyendo al líder).\nSe encontraron: **{len(all_members)}** (Recuerda que el primer argumento es el nombre del equipo).", discord.Color.red(), author=ctx.author))
             return
             
        current_teams_count = len(await DBManager.get_teams(tourney_id))
        max_t = active_tourney.get('max_teams', 16)
        if current_teams_count >= max_t:
             await ctx.send(embed=self.get_embed("Error", "El torneo ha alcanzado el límite de equipos.", discord.Color.red(), author=ctx.author))
             return

        member_ids = [m.id for m in all_members]
        
        if not hasattr(self, 'pending_teams'):
            self.pending_teams = {}
        
        pending_id = str(uuid.uuid4())
        self.pending_teams[pending_id] = {
            "tourney_id": tourney_id,
            "name": name,
            "leader_id": ctx.author.id,
            "members": member_ids,
            "confirmed": [ctx.author.id],
            "message_ids": []
        }
        
        confirm_view = ConfirmRegistrationView(self.bot, pending_id, self)
        
        msgs_sent = 0
        for member in all_members:
            if member.id == ctx.author.id:
                continue 
            
            try:
                await member.send(
                    embed=self.get_embed("Invitación a Equipo", f"Has sido invitado al equipo **{name}** para el torneo **{active_tourney['name']}**.\nConfirma para unirte.", author=ctx.author),
                    view=confirm_view
                )
                msgs_sent += 1
                await self.send_log(
                    ctx.guild, tourney_id,
                    "📩 Invitación Enviada (DM)",
                    f"**Destinatario:** {member.mention}\n**Equipo:** {name}\n**Torneo:** {active_tourney['name']}",
                    discord.Color(0xFFC0CB)
                )
            except discord.Forbidden:
                await ctx.send(f"No pude enviar MD a {member.mention}. Asegúrate de que tengan los MDs abiertos.")
                del self.pending_teams[pending_id]
                return

        if msgs_sent == 0:
            await self.create_team_final(pending_id)
            await ctx.send(embed=self.get_embed("Registro Completado", f"Equipo **{name}** registrado (Solo tú).", author=ctx.author))
        else:
            await ctx.send(embed=self.get_embed("Solicitud Enviada", f"Se ha enviado petición de confirmación a los miembros. El equipo se creará cuando todos acepten.", author=ctx.author))

    async def create_team_final(self, pending_id):
        """
        Crea el equipo en la base de datos
        """ 
        if pending_id not in self.pending_teams: return
        data = self.pending_teams[pending_id]
        
        new_team = {
            "id": str(uuid.uuid4())[:8],
            "name": data['name'],
            "members": data['members'],
            "leader_id": data['leader_id'],
            "tournament_id": data['tourney_id']
        }
        await DBManager.create_team(new_team)
        
        tourney = await DBManager.get_tournament(data['tourney_id'])
        guild = self.bot.get_guild(tourney['guild_id']) if tourney else None

        for uid in data['members']:
            user = self.bot.get_user(uid)
            if not user:
                try:
                    user = await self.bot.fetch_user(uid)
                except:
                    continue
            
            if user:
                try:
                    embed = self.get_embed("Equipo Creado", f"El equipo **{data['name']}** ha sido registrado exitosamente.\nTorneo ID: {data['tourney_id']}", discord.Color.green(), author=user)
                    embed.add_field(name="Líder", value=f"<@{data['leader_id']}>")
                    members_mentions = "\n".join([f"<@{m}>" for m in data['members']])
                    embed.add_field(name="Miembros", value=members_mentions)
                    await user.send(embed=embed)
                    
                    if guild:
                        await self.send_log(
                            guild, data['tourney_id'],
                            "✅ Confirmación de Equipo (DM)",
                            f"**Destinatario:** <@{uid}>\n**Equipo:** {data['name']}\n**Torneo:** {data['tourney_id']}",
                            discord.Color(0xFFC0CB)
                        )
                except discord.Forbidden:
                    pass 

        if guild:
            members_str = ", ".join([f"<@{m}>" for m in data['members']])
            await self.send_log(
                guild, data['tourney_id'],
                "👥 Equipo Creado",
                f"**{data['name']}**\n\n**Líder:** <@{data['leader_id']}>\n**Miembros:** {members_str}",
                discord.Color.blue()
            )

        # Asignar rol de participante a todo el equipo
        if guild:
            await self.assign_participant_role(guild, data['members'])

        del self.pending_teams[pending_id]
        
    @tourney.command(name="invite")
    async def invite_member(self, ctx, user: discord.Member):
        """
        Invita a un usuario a tu equipo (solo el líder puede invitar)
        """ 
        active_tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not active_tourney:
            await ctx.send(embed=self.get_embed("Error", "No hay ningún torneo activo en este servidor.", discord.Color.red(), author=ctx.author))
            return
        
        if active_tourney['status'] != "open":
            await ctx.send(embed=self.get_embed("Error", "El torneo no está abierto para nuevos miembros.", discord.Color.red(), author=ctx.author))
            return
        
        team = await DBManager.get_team_by_member(ctx.author.id, active_tourney['id'])
        if not team:
            await ctx.send(embed=self.get_embed("Error", "No perteneces a ningún equipo en el torneo activo.", discord.Color.red(), author=ctx.author))
            return
            
        if team['leader_id'] != ctx.author.id:
            await ctx.send(embed=self.get_embed("Error", "Solo el líder del equipo puede invitar miembros.", discord.Color.red(), author=ctx.author))
            return
        
        max_m = active_tourney.get('max_members', 5)
        if len(team['members']) >= max_m:
            await ctx.send(embed=self.get_embed("Error", f"El equipo ya tiene el máximo de miembros permitidos ({max_m}).", discord.Color.red(), author=ctx.author))
            return
            
        bl_entry = await DBManager.get_blacklisted_user(ctx.guild.id, user.id)
        if bl_entry:
            await ctx.send(embed=self.get_embed("Blacklist", f"El usuario {user.mention} está en la blacklist y no puede participar.\n**Motivo:** {bl_entry.get('reason', 'Sin especificar')}", discord.Color.red(), author=ctx.author))
            return
             
        existing_team = await DBManager.get_team_by_member(user.id, team['tournament_id'])
        if existing_team:
             await ctx.send(embed=self.get_embed("Error", f"El usuario {user.mention} ya está en el equipo **{existing_team['name']}**.", discord.Color.red(), author=ctx.author))
             return

        view = ConfirmInviteView(self.bot, team['id'], user.id, self)
        try:
            await user.send(
                embed=self.get_embed("Invitación", f"Te han invitado a unirte al equipo **{team['name']}** en el torneo **{active_tourney['name']}**.", author=ctx.author),
                view=view
            )
            await self.send_log(
                ctx.guild, active_tourney['id'],
                "📩 Invitación a Unirse (DM)",
                f"**Destinatario:** {user.mention}\n**Equipo:** {team['name']}\n**Enviado por:** {ctx.author.mention}",
                discord.Color(0xFFC0CB)
            )
            await ctx.send(embed=self.get_embed("Invitación Enviada", f"Se ha enviado invitación a {user.mention} para unirse al equipo **{team['name']}**.", author=ctx.author))
        except:
             await ctx.send(embed=self.get_embed("Error", f"No se pudo enviar MD a {user.mention}. Asegúrate de que tenga los MDs abiertos.", discord.Color.red(), author=ctx.author))

    @tourney.command(name="leave")
    async def leave_team(self, ctx):
        """
        Abandona el equipo actual
        """ 
        active_tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not active_tourney:
             await ctx.send(embed=self.get_embed("Error", "No hay torneo activo.", discord.Color.red(), author=ctx.author))
             return
        
        if active_tourney['status'] != 'open':
             await ctx.send(embed=self.get_embed("Error", "El torneo no está abierto.", discord.Color.red(), author=ctx.author))
             return
             
        team = await DBManager.get_team_by_member(ctx.author.id, active_tourney['id'])
        if not team:
            await ctx.send(embed=self.get_embed("Error", "No perteneces a ningún equipo.", discord.Color.red(), author=ctx.author))
            return
            
        if len(team['members']) == 1:
            await DBManager.delete_team(team['id'])
            # Quitar rol de participante
            await self.remove_participant_role(ctx.guild, [ctx.author.id])
            await self.send_log(
                ctx.guild, active_tourney['id'],
                "🗑️ Equipo Disuelto",
                f"**{team['name']}** ha sido eliminado porque su único miembro {ctx.author.mention} lo abandonó.",
                discord.Color.orange()
            )
            await ctx.send(embed=self.get_embed("Equipo Abandonado", f"Has abandonado el equipo **{team['name']}**. Al ser el último miembro, el equipo ha sido eliminado.", author=ctx.author))
            return
            
        team['members'].remove(ctx.author.id)
        update_data = {"members": team['members']}
        msg_extra = ""
        
        if team['leader_id'] == ctx.author.id:
            new_leader_id = team['members'][0]
            team['leader_id'] = new_leader_id
            update_data['leader_id'] = new_leader_id
            msg_extra = f"\nEl liderazgo ha pasado a <@{new_leader_id}>."
            
        await DBManager.update_team(team['id'], update_data)
        
        # Quitar rol de participante al miembro que sale
        await self.remove_participant_role(ctx.guild, [ctx.author.id])
        
        await self.send_log(
            ctx.guild, active_tourney['id'],
            "👋 Miembro Salió",
            f"**{ctx.author.mention}** abandonó el equipo **{team['name']}**.{msg_extra}",
            discord.Color.orange()
        )
        
        await ctx.send(embed=self.get_embed("Equipo Abandonado", f"Has abandonado el equipo **{team['name']}**.{msg_extra}", author=ctx.author))

    async def resolve_team(self, target: str, tournament_id: str):
        """Resuelve un equipo por su ID o por la mención/ID de uno de sus miembros."""
        target = (target or "").strip()
        if not target:
            return None
        team = await DBManager.get_team(target)
        if team and team.get('tournament_id') == tournament_id:
            return team
        user_id = None
        if target.startswith("<@") and target.endswith(">"):
            try:
                user_id = int(target.replace("<@", "").replace("!", "").replace("&", "").replace(">", ""))
            except ValueError:
                user_id = None
        else:
            try:
                user_id = int(target)
            except ValueError:
                user_id = None
        if user_id:
            return await DBManager.get_team_by_member(user_id, tournament_id)
        return None

    @tourney.command(name="rename")
    async def rename_team(self, ctx, *, args: str):
        """
        Cambia el nombre de un equipo.
        - Líder: `,tourney rename <nuevo_nombre>` (solo antes de iniciar).
        - Organizador/Admin: `,tourney rename <id_equipo|@miembro> | <nuevo_nombre>` (cualquier equipo).
        """
        active_tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not active_tourney:
            await ctx.send(embed=self.get_embed("Error", "No hay ningún torneo activo en este servidor.", discord.Color.red(), author=ctx.author))
            return

        args = args.strip()

        if "|" in args:
            # Variante Organizador/Admin: renombra cualquier equipo
            if not await self.admin_check(ctx):
                return
            target_str, _, new_name = args.partition("|")
            new_name = new_name.strip()
            team = await self.resolve_team(target_str, active_tourney['id'])
            if not team:
                await ctx.send(embed=self.get_embed("Error", "No se encontró el equipo. Usa el ID del equipo o menciona a uno de sus miembros.", discord.Color.red(), author=ctx.author))
                return
        else:
            # Variante Líder: renombra su propio equipo (solo antes de iniciar)
            new_name = args.strip()
            team = await DBManager.get_team_by_member(ctx.author.id, active_tourney['id'])
            if not team:
                await ctx.send(embed=self.get_embed("Error", "No perteneces a ningún equipo en el torneo activo.", discord.Color.red(), author=ctx.author))
                return
            if team['leader_id'] != ctx.author.id:
                await ctx.send(embed=self.get_embed("Error", "Solo el **líder** del equipo puede cambiar el nombre.\nSi eres organizador, usa `rename <id/@miembro> | <nombre>`.", discord.Color.red(), author=ctx.author))
                return
            if active_tourney['status'] not in ("open", "pending"):
                await ctx.send(embed=self.get_embed("Error", "Solo puedes renombrar tu equipo antes de que el torneo inicie.", discord.Color.red(), author=ctx.author))
                return

        if not new_name:
            await ctx.send(embed=self.get_embed("Error", "Debes indicar un nombre.", discord.Color.red(), author=ctx.author))
            return

        if new_name.startswith("<@") or new_name.startswith("<#") or new_name.startswith("<@&"):
            await ctx.send(embed=self.get_embed("Error", "El nombre del equipo no puede ser una mención.", discord.Color.red(), author=ctx.author))
            return

        if len(new_name) > MAX_TEAM_NAME_LEN:
            await ctx.send(embed=self.get_embed("Error", f"El nombre del equipo no puede superar los {MAX_TEAM_NAME_LEN} caracteres.", discord.Color.red(), author=ctx.author))
            return

        if new_name == team['name']:
            await ctx.send(embed=self.get_embed("Error", "El nuevo nombre es igual al actual.", discord.Color.red(), author=ctx.author))
            return

        existing = await DBManager.get_team_by_name(new_name, active_tourney['id'])
        if existing and existing['id'] != team['id']:
            await ctx.send(embed=self.get_embed("Error", "Ya existe un equipo con ese nombre en este torneo.", discord.Color.red(), author=ctx.author))
            return

        old_name = team['name']
        await DBManager.update_team(team['id'], {"name": new_name})

        await self.send_log(
            ctx.guild, active_tourney['id'],
            "✏️ Equipo Renombrado",
            f"**{old_name}** → **{new_name}**\n\n**Por:** {ctx.author.mention}",
            discord.Color.blue()
        )

        await ctx.send(embed=self.get_embed("Equipo Renombrado", f"El nombre del equipo ha cambiado de **{old_name}** a **{new_name}**.", discord.Color.green(), author=ctx.author))

    @tourney.command(name="kick")
    async def kick_team(self, ctx, target: str):
        """
        Expulsa a un equipo del torneo
        """ 
        if not await self.admin_check(ctx): return
        
        tourney = await DBManager.get_active_tournament(ctx.guild.id)
        if not tourney:
             await ctx.send(embed=self.get_embed("Error", "No hay torneo activo.", discord.Color.red(), author=ctx.author))
             return
        
        team = None
        
        if tourney['status'] == 'active':
            await ctx.send(embed=self.get_embed("Error", "El torneo ya está en curso.", discord.Color.red(), author=ctx.author))
            return

        team = await DBManager.get_team(target)
        
        if team and team['tournament_id'] != tourney['id']:
            team = None
            
        if not team:
            user_id = None
            if target.startswith("<@") and target.endswith(">"):
                try:
                    user_id = int(target.replace("<@", "").replace("!", "").replace("&", "").replace(">", ""))
                except:
                    pass
            else:
                try:
                    user_id = int(target)
                except ValueError:
                    pass
            
            if user_id:
                team = await DBManager.get_team_by_member(user_id, tourney['id'])

        if not team:
            await ctx.send(embed=self.get_embed("Error", "No se encontró el equipo. Asegúrate de usar el ID del equipo o mencionar a un miembro válido.", discord.Color.red(), author=ctx.author))
            return
        
        team_name = team['name']
        team_id = team['id']
        team_members = team.get('members', [])
        await DBManager.delete_team(team_id)
        
        # Quitar rol de participante a todos los miembros del equipo kickeado
        await self.remove_participant_role(ctx.guild, team_members)
        
        await self.send_log(
            ctx.guild, tourney['id'],
            "🗑️ Equipo Eliminado",
            f"**{team_name}**\n\n**Eliminado por:** {ctx.author.mention}",
            discord.Color.orange()
        )
        
        await ctx.send(embed=self.get_embed("Equipo Eliminado", f"El equipo **{team_name}** ha sido expulsado del torneo.", author=ctx.author))

    @tourney.command(name="teams")
    async def list_teams(self, ctx, tourney_id: str = None):
        """
        Lista los equipos del torneo
        """ 
        if not tourney_id:
             t = await DBManager.get_active_tournament(ctx.guild.id)
             if t: tourney_id = t['id']
        
        if not tourney_id:
             await ctx.send(embed=self.get_embed("Error", "Especifica ID de torneo o ten uno activo.", discord.Color.red(), author=ctx.author))
             return

        teams = await DBManager.get_teams(tourney_id)
        if not teams:
             await ctx.send(embed=self.get_embed("Equipos", "No hay equipos registrados.", discord.Color.red(), author=ctx.author))
             return
             
        desc = ""
        for team in teams:
            leader_name = f"<@{team['leader_id']}>"
            desc += f"**{team['name']}** (ID: `{team['id']}`) - Líder: {leader_name} - Miembros: {len(team['members'])}\n"
            
        await ctx.send(embed=self.get_embed(f"Equipos Registrados ({len(teams)})", desc, author=ctx.author))

    @tourney.command(name="team")
    async def team_info(self, ctx, target: str = None):
        """
        Muestra información del equipo
        """ 
        team = None
        user_id = None
        
        if target is None:
             user_id = ctx.author.id
        else:
            if ctx.message.mentions:
                user_id = ctx.message.mentions[0].id
            else:
                try:
                    user_id = int(target)
                except ValueError:
                    pass
            
            team = await DBManager.get_team(target)
        
        if not team and user_id:
            active_t = await DBManager.get_active_tournament(ctx.guild.id)
            if active_t:
                team = await DBManager.get_team_by_member(user_id, active_t['id'])
        
        if not team:
            msg = "Equipo no encontrado o usuario no está en un equipo del torneo activo."
            if target is None:
                 msg = "No perteneces a ningún equipo en el torneo activo."
            await ctx.send(embed=self.get_embed("Error", msg, discord.Color.red(), author=ctx.author))
            return
            
        members_str = ", ".join([f"<@{m}>" for m in team['members']])
        embed = self.get_embed(f"Info Equipo: {team['name']}", f"ID: {team['id']}\nLíder: <@{team['leader_id']}>", author=ctx.author)
        embed.add_field(name="Miembros", value=members_str)
        
        await ctx.send(embed=embed)

    @tourney.command(name="bug")
    async def report_bug(self, ctx, *, description: str):
        """
        Reporta un bug o problema del bot
        """ 
        bug_channel = self.bot.get_channel(BUG_CHANNEL)
        if not bug_channel:
            await ctx.send(embed=self.get_embed("Error", "No se pudo encontrar el canal de bugs.", discord.Color.red(), author=ctx.author))
            return
        
        embed = discord.Embed(
            title="🐛 Reporte de Bug",
            description=description,
            color=discord.Color.red()
        )
        embed.add_field(name="Servidor", value=f"{ctx.guild.name} ({ctx.guild.id})", inline=False)
        embed.add_field(name="Reportado por", value=f"{ctx.author.mention} ({ctx.author.name})", inline=False)
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text=f"User ID: {ctx.author.id}")
        
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        
        # await bug_channel.send(embed=embed) # Don't send directly
        
        try:
            report_data = {
                "description": description,
                "user_name": f"{ctx.author.mention} ({ctx.author.name})",
                "server_id": ctx.guild.id,
                "server_name": ctx.guild.name,
                "source": "Discord"
            }
            await DBManager.create_bug_report(report_data)

            # Entrega inmediata al canal de bugs (sin esperar al loop)
            reports_cog = self.bot.get_cog("Reports")
            if reports_cog:
                try:
                    await reports_cog.deliver_reports()
                except Exception as e:
                    print(f"[Reports] Error en entrega inmediata de bug: {e}")

            confirm_msg = await ctx.send(embed=self.get_embed("Bug Reportado", "Tu reporte ha sido guardado. ¡Gracias por ayudar a mejorar el bot!", discord.Color.green(), author=ctx.author))
            
            active_t = await DBManager.get_active_tournament(ctx.guild.id)
            tourney_id = active_t['id'] if active_t else "N/A"
            
            channel_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}"
            message_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{ctx.message.id}"
            
            await self.send_log(
                ctx.guild, tourney_id,
                "🐛 Bug Registrado",
                f"**Descripción:** {description}\n\n**Reportado por:** {ctx.author.mention}\n**Canal:** [#{ctx.channel.name}]({channel_link})\n**Mensaje:** [Ver mensaje]({message_link})",
                discord.Color.red()
            )
        except Exception as e:
            await ctx.send(embed=self.get_embed("Error", "Ocurrió un error al guardar el reporte.", discord.Color.red(), author=ctx.author))
            print(f"Error saving bug: {e}")


class ConfirmRegistrationView(discord.ui.View):
    def __init__(self, bot, pending_id, cog):
        super().__init__(timeout=300)
        self.bot = bot
        self.pending_id = pending_id
        self.cog = cog

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.pending_id not in self.cog.pending_teams:
            await interaction.response.send_message("Esta invitación ha expirado o el equipo ya se formó/canceló.", ephemeral=True)
            return

        data = self.cog.pending_teams[self.pending_id]
        if interaction.user.id in data['confirmed']:
            await interaction.response.send_message("Ya has confirmado.", ephemeral=True)
            return

        existing = await DBManager.get_team_by_member(interaction.user.id, data['tourney_id'])
        if existing:
             await interaction.response.send_message(f"Ya perteneces al equipo **{existing['name']}**. No puedes unirte a este.", ephemeral=True)
             return

        data['confirmed'].append(interaction.user.id)
        await interaction.response.send_message("Has aceptado unirte al equipo.", ephemeral=True)
        
        if all(uid in data['confirmed'] for uid in data['members']):
            self.stop()
            try:
                await self.cog.create_team_final(self.pending_id)
            except Exception as e:
                import traceback
                traceback.print_exc()

class ConfirmInviteView(discord.ui.View):
    def __init__(self, bot, team_id, user_id, cog):
        super().__init__(timeout=300)
        self.bot = bot
        self.team_id = team_id
        self.user_id = user_id
        self.cog = cog

    @discord.ui.button(label="Unirse", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
             return
             
        team = await DBManager.get_team(self.team_id)
        if not team:
            await interaction.response.send_message("El equipo ya no existe.", ephemeral=True)
            return
            
        if interaction.user.id in team['members']:
             await interaction.response.send_message("Ya estás en el equipo.", ephemeral=True)
             return
             
        existing = await DBManager.get_team_by_member(interaction.user.id, team['tournament_id'])
        if existing:
             await interaction.response.send_message(f"Ya perteneces al equipo **{existing['name']}**. No puedes unirte a este.", ephemeral=True)
             return
             
        team['members'].append(interaction.user.id)
        from utils.db import teams_collection
        await teams_collection.update_one({"id": self.team_id}, {"$set": {"members": team['members']}})
        
        # Asignar rol de participante al nuevo miembro
        tourney_data = await DBManager.get_tournament(team['tournament_id'])
        if tourney_data:
            invite_guild = self.bot.get_guild(tourney_data['guild_id'])
            if invite_guild:
                await self.cog.assign_participant_role(invite_guild, [interaction.user.id])
        
        tourney = await DBManager.get_tournament(team['tournament_id'])
        if tourney:
            guild = self.bot.get_guild(tourney['guild_id'])
            if guild:
                await self.cog.send_log(
                    guild, team['tournament_id'],
                    "➕ Miembro Unido",
                    f"**{team['name']}**\n\n**Nuevo miembro:** {interaction.user.mention}\n**Total miembros:** {len(team['members'])}",
                    discord.Color.blue()
                )
        
        await interaction.response.send_message(f"Te has unido a **{team['name']}**!", ephemeral=True)
        self.stop()


class MatchReportView(discord.ui.View):
    """
    Vista persistente para reportar el resultado de un enfrentamiento desde su canal.
    Los custom_id son estáticos: el enfrentamiento se localiza por el canal donde se
    pulsa el botón, de modo que siguen funcionando tras un reinicio del bot.
    """
    def __init__(self, cog, team1_name: str = "Equipo 1", team2_name: str = "Equipo 2"):
        super().__init__(timeout=None)
        self.cog = cog
        # Etiquetas dinámicas con los nombres reales; los custom_id se mantienen fijos.
        self.report_team1.label = f"🏆 {team1_name[:60]}"
        self.report_team2.label = f"🏆 {team2_name[:60]}"

    @discord.ui.button(label="🏆 Equipo 1", style=discord.ButtonStyle.success, custom_id="match_report:team1")
    async def report_team1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_match_report(interaction, "team1")

    @discord.ui.button(label="🏆 Equipo 2", style=discord.ButtonStyle.success, custom_id="match_report:team2")
    async def report_team2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_match_report(interaction, "team2")

    @discord.ui.button(label="Anular reporte", style=discord.ButtonStyle.secondary, custom_id="match_report:cancel")
    async def cancel_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_match_cancel(interaction)


async def setup(bot):
    await bot.add_cog(Tourney(bot))