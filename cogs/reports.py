import discord
from discord.ext import commands, tasks
from config import BUG_CHANNEL, SUGGESTION_CHANNEL
from utils.db import DBManager
import datetime

class Reports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.report_loop.start()

    def cog_unload(self):
        self.report_loop.cancel()

    # Intervalo corto: los reportes creados desde la WEB se entregan casi al instante.
    # Los creados desde el BOT se entregan inmediatamente vía deliver_reports() (sin esperar al loop).
    @tasks.loop(seconds=15)
    async def report_loop(self):
        await self.process_bugs()
        await self.process_suggestions()

    async def deliver_reports(self):
        """Procesa y entrega de inmediato los reportes pendientes (bugs y sugerencias)."""
        await self.process_bugs()
        await self.process_suggestions()

    @report_loop.before_loop
    async def before_report_loop(self):
        await self.bot.wait_until_ready()

    async def process_bugs(self):
        try:
            bugs = await DBManager.get_unsent_bugs()
            channel = self.bot.get_channel(BUG_CHANNEL)
            
            if not channel:
                return

            for bug in bugs:
                try:
                    embed = discord.Embed(
                        title="Nuevo Reporte de Bug",
                        description=bug['description'],
                        color=discord.Color.orange(),
                        timestamp=bug.get('timestamp', datetime.datetime.now(datetime.timezone.utc))
                    )
                    
                    user_info = bug.get('user_name', 'Desconocido')
                    
                    server_name = bug.get('server_name')
                    server_id = bug.get('server_id')

                    server_info = f"{server_name} ({server_id})" if server_name else f"ID: {server_id}"
                    via_info = bug.get('source', 'Desconocido')

                    if server_id:
                        via_info = f"{via_info} - {server_info}"
                    
                    embed.add_field(name="``VIA``", value=via_info, inline=False)
                    embed.add_field(name="``Reportado por``", value=user_info, inline=False)
                    embed.set_footer(text=f"ID: {bug['_id']}")

                    await channel.send(embed=embed)
                    await DBManager.mark_bug_as_sent(bug['_id'])
                    
                except Exception as e:
                    print(f"Error sending bug report {bug.get('_id')}: {e}")

        except Exception as e:
            print(f"Error in process_bugs: {e}")

    async def process_suggestions(self):
        try:
            suggestions = await DBManager.get_unsent_suggestions()
            channel = self.bot.get_channel(SUGGESTION_CHANNEL)
            
            if not channel:
                # print(f"Suggestion Channel ({SUGGESTION_CHANNEL}) not found")
                return

            for sug in suggestions:
                try:
                    embed = discord.Embed(
                        title="Nueva Sugerencia",
                        description=sug['description'],
                        color=discord.Color.gold(),
                        timestamp=sug.get('timestamp', datetime.datetime.now(datetime.timezone.utc))
                    )
                    
                    user_info = sug.get('user_name', 'Desconocido')
                    
                    server_name = sug.get('server_name')
                    server_id = sug.get('server_id')
                    
                    server_info = f"{server_name} ({server_id})" if server_name else f"ID: {server_id}"
                    via_info = sug.get('source', 'Desconocido')

                    if server_id:
                        via_info = f"{via_info} - {server_info}"
                    
                    embed.add_field(name="``VIA``", value=via_info, inline=False)
                    embed.add_field(name="``Sugerido por``", value=user_info, inline=False)
                    embed.set_footer(text=f"ID: {sug['_id']}")

                    await channel.send(embed=embed)
                    await DBManager.mark_suggestion_as_sent(sug['_id'])
                    
                except Exception as e:
                    print(f"Error sending suggestion {sug.get('_id')}: {e}")

        except Exception as e:
            print(f"Error in process_suggestions: {e}")

async def setup(bot):
    await bot.add_cog(Reports(bot))
