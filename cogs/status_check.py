import discord
from discord.ext import commands, tasks
from utils.db import DBManager

class StatusCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.heartbeat_loop.start()

    def cog_unload(self):
        self.heartbeat_loop.cancel()

    @tasks.loop(seconds=30)
    async def heartbeat_loop(self):
        try:
            # Latency is in seconds, convert to ms
            latency = round(self.bot.latency * 1000, 2)
            await DBManager.update_heartbeat(latency)
        except Exception as e:
            print(f"Heartbeat Error: {e}")

    @heartbeat_loop.before_loop
    async def before_heartbeat_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(StatusCheck(bot))
