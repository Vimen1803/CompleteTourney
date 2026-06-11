import discord
from discord.ext import commands
from config import OWNER
from utils.db import DBManager

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner(self, ctx):
        return ctx.author.id in OWNER

    @commands.command(name="leaveserver")
    async def leaveserver(self, ctx, guild_id: int):
        """
        Se ejecuta cuando el bot es eliminado de un servidor.
        Se encarga de eliminar el servidor de la base de datos y enviar un mensaje al canal de serverlogs.
        """
        if not self.is_owner(ctx):
            await ctx.send("No tienes permisos para ejecutar este comando.")
            return

        guild = self.bot.get_guild(guild_id)
        if guild:
            try:
                await guild.leave()
                embed = discord.Embed(
                    title="👋 Servidor Abandonado",
                    description=f"He abandonado el servidor: **{guild.name}**\nID: `{guild.id}`",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Error al abandonar el servidor: `{e}`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ No encontrado",
                description="No estoy en ese servidor o la ID es inválida.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="servers", aliases=["serverlist"])
    async def servers(self, ctx):
        """
        Se ejecuta cuando el bot es eliminado de un servidor.
        Se encarga de eliminar el servidor de la base de datos y enviar un mensaje al canal de serverlogs.
        """
        if not self.is_owner(ctx):
            await ctx.send("No tienes permisos para ejecutar este comando.")
            return

        embed = discord.Embed(title="Lista de Servidores", color=discord.Color.blue())
        
        description = ""
        count = 0
        
        fields = []
        for guild in self.bot.guilds:
            invite_url = "No disponible"
            
            config = await DBManager.get_or_create_guild_config(guild.id)
            if config.get('invite_url'):
                invite_url = config.get('invite_url')
            else:
                try:
                    target_ch = guild.system_channel or next(
                        (c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), 
                        None
                    )
                    if target_ch:
                        inv = await target_ch.create_invite(max_age=0, max_uses=0, reason="Admin request")
                        invite_url = inv.url
                        await DBManager.update_guild_config_field(guild.id, 'invite_url', invite_url)
                except Exception as e:
                    print(f"[servers] No se pudo crear invitación para {guild.name}: {e}")

            if invite_url.startswith("http"):
                value_str = f"`{guild.id}`\n[Ir al servidor]({invite_url})"
            else:
                value_str = f"`{guild.id}`\nSin invitación"

            fields.append({"name": guild.name, "value": value_str})

        chunks = [fields[i:i + 10] for i in range(0, len(fields), 10)]
        
        if not chunks:
             await ctx.send(embed=discord.Embed(title="No estoy en ningún servidor.", color=discord.Color.red()))
             return

        for i, chunk in enumerate(chunks):
            title = f"Lista de Servidores ({len(self.bot.guilds)})" if i == 0 else f"Lista de Servidores (Parte {i+1})"
            embed = discord.Embed(title=title, color=discord.Color.blue())
            
            for field in chunk:
                embed.add_field(name=field["name"], value=field["value"], inline=False)
            
            await ctx.send(embed=embed)

    @commands.command(name="isinserver")
    async def isinserver(self, ctx, guild_id: int):
        """
        Revisa si el bot está en un servidor con la ID proporcionada y da información sobre el servidor.
        """
        if not self.is_owner(ctx):
            await ctx.send("No tienes permisos.")
            return

        guild = self.bot.get_guild(guild_id)
        
        if not guild:
            embed = discord.Embed(
                title="❌ No encontrado",
                description=f"El bot NO está en el servidor con ID `{guild_id}`.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            total_members = guild.member_count
            online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)
            
            created_ts = int(guild.created_at.timestamp())
            date_str = f"<t:{created_ts}:f>"
            relative_str = f"<t:{created_ts}:R>"
            
            embed = discord.Embed(title=f"{guild.name}", description=f"Created on {date_str}. Eso es {relative_str}!", color=discord.Color.blue())
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.add_field(name="Users online", value=f"{online_members}/{total_members}", inline=True)
            
            embed.add_field(name="Owner", value=f"{guild.owner}", inline=True)

            joined_ts = int(guild.me.joined_at.timestamp())
            embed.add_field(name="Joined", value=f"<t:{joined_ts}:f> (<t:{joined_ts}:R>)", inline=False)
            
            embed.set_footer(text=f"Server ID: {guild.id}")
            
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))