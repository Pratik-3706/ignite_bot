import psutil
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from src.config import ADMIN_USER_IDS, ADMIN_ROLE_NAME
from src.utils.ai_client import ask_ai
from src.utils.tools.web_search import search_web
from src.utils.tools.pdf_maker import create_pdf_document
from src.utils.tools.events import add_event, get_events, remove_event
from src.utils.memory.memory import memory_manager

def is_admin_user(user: discord.Member | discord.User) -> bool:
    if user.id in ADMIN_USER_IDS:
        return True
    if isinstance(user, discord.Member):
        if user.guild_permissions.administrator or user.guild_permissions.manage_guild:
            return True
        for role in user.roles:
            if role.name.lower() == ADMIN_ROLE_NAME:
                return True
    return False

def admin_check():
    async def predicate(ctx: commands.Context) -> bool:
        if not is_admin_user(ctx.author):
            await ctx.reply("Permission denied. Only admins can use this command.", mention_author=False)
            return False
        return True
    return commands.check(predicate)

async def send_chunked_message(channel: discord.abc.Messageable, text: str, 
                               reference: Optional[discord.Message] = None, 
                               file: Optional[discord.File] = None):
    max_len = 1900
    if len(text) <= max_len:
        if reference:
            await reference.reply(text, file=file, mention_author=False)
        else:
            await channel.send(text, file=file)
        return

    # Split into chunks
    lines = text.split("\n")
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_len:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk:
        chunks.append(current_chunk)

    first = True
    for chunk in chunks:
        if first:
            if reference:
                await reference.reply(chunk, file=file, mention_author=False)
            else:
                await channel.send(chunk, file=file)
            first = False
        else:
            await channel.send(chunk)

class BotCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ask")
    async def ask_cmd(self, ctx: commands.Context, *, prompt: str):
        async with ctx.typing():
            res = await ask_ai(
                channel_id=ctx.channel.id,
                guild_id=ctx.guild.id if ctx.guild else None,
                user_id=ctx.author.id,
                user_name=ctx.author.display_name,
                prompt=prompt
            )

        file_obj = None
        if res.get("pdf_path") and res["pdf_path"].exists():
            file_obj = discord.File(str(res["pdf_path"]))

        await send_chunked_message(ctx.channel, res["text"], reference=ctx.message, file=file_obj)

        if res.get("pdf_path") and res["pdf_path"].exists():
            try:
                res["pdf_path"].unlink()
            except Exception:
                pass

    @commands.command(name="search")
    async def search_cmd(self, ctx: commands.Context, *, query: str):
        async with ctx.typing():
            results = await search_web(query)
            embed = discord.Embed(title=f"Web Search: {query}", description=results[:4000], color=0x3498DB)
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="pdf")
    async def pdf_cmd(self, ctx: commands.Context, *, args: str):
        parts = args.split("|", 1)
        title = parts[0].strip()
        body = parts[1].strip() if len(parts) > 1 else title

        async with ctx.typing():
            pdf_path = await create_pdf_document(title, body)
            try:
                await ctx.reply(
                    f"Generated PDF: **{title}**",
                    file=discord.File(str(pdf_path)),
                    mention_author=False
                )
            finally:
                if pdf_path.exists():
                    pdf_path.unlink()

    @commands.group(name="event", invoke_without_command=True)
    async def event_group(self, ctx: commands.Context):
        guild_id = ctx.guild.id if ctx.guild else ctx.author.id
        events = await get_events(guild_id)
        if not events:
            await ctx.reply("No upcoming club events found.", mention_author=False)
            return

        embed = discord.Embed(title="Ignite Club Events", color=0xE67E22)
        for ev in events:
            val = f"**Date:** {ev['date_time']}\n{ev.get('details', '')}\n*(Added by <@{ev['created_by']}>)*"
            embed.add_field(name=f"#{ev['id']} - {ev['title']}", value=val, inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @event_group.command(name="add")
    @admin_check()
    async def event_add(self, ctx: commands.Context, title: str, date_time: str, *, details: str = ""):
        guild_id = ctx.guild.id if ctx.guild else ctx.author.id
        ev_id = await add_event(guild_id, title, details, date_time, str(ctx.author.id))
        await ctx.reply(f"Event **{title}** added with ID #{ev_id}.", mention_author=False)

    @event_group.command(name="remove")
    @admin_check()
    async def event_remove(self, ctx: commands.Context, event_id: int):
        guild_id = ctx.guild.id if ctx.guild else ctx.author.id
        deleted = await remove_event(guild_id, event_id)
        if deleted:
            await ctx.reply(f"Event #{event_id} removed.", mention_author=False)
        else:
            await ctx.reply(f"Event #{event_id} not found.", mention_author=False)

    @commands.command(name="setclub")
    @admin_check()
    async def setclub_cmd(self, ctx: commands.Context, key: str, *, value: str):
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.", mention_author=False)
            return
        await memory_manager.set_club_memory(ctx.guild.id, key, value, ctx.author.display_name)
        await ctx.reply(f"Saved club memory: **{key}**.", mention_author=False)

    @commands.command(name="clear")
    @admin_check()
    async def clear_memory_cmd(self, ctx: commands.Context):
        await memory_manager.clear_channel_history(ctx.channel.id)
        await ctx.reply("Channel conversation memory cleared.", mention_author=False)

    @commands.command(name="status")
    @admin_check()
    async def status_cmd(self, ctx: commands.Context):
        stats = await memory_manager.get_stats()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(".")

        ram_used_mb = mem.used / (1024 * 1024)
        ram_total_mb = mem.total / (1024 * 1024)
        disk_used_mb = disk.used / (1024 * 1024)
        disk_total_mb = disk.total / (1024 * 1024)

        desc = (
            f"**RAM:** {ram_used_mb:.1f} / {ram_total_mb:.1f} MB ({mem.percent}%)\n"
            f"**Disk:** {disk_used_mb:.1f} / {disk_total_mb:.1f} MB ({disk.percent}%)\n"
            f"**Total Channel Messages:** {stats['total_messages']}\n"
            f"**Unique Users Tagged:** {stats['unique_users']}\n"
            f"**Club Memories:** {stats['club_memories']}\n"
            f"**Events:** {stats['events']}\n"
            f"**SQLite DB Size:** {stats['db_size_kb']} KB\n"
            f"**Latency:** {round(self.bot.latency * 1000)}ms"
        )
        embed = discord.Embed(title="System & Bot Status", description=desc, color=0x2ECC71)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="help")
    async def help_cmd(self, ctx: commands.Context):
        text = (
            "**Ignite Bot Commands**\n"
            "`!ng ask <prompt>` - Ask AI assistant with context memory & tools\n"
            "`!ng search <query>` - Web search via Tavily\n"
            "`!ng pdf <title> | <content>` - Generate PDF document\n"
            "`!ng event` - List club events\n\n"
            "**Admin Commands:**\n"
            "`!ng event add <title> <date_time> [details]` - Add club event\n"
            "`!ng event remove <id>` - Remove club event\n"
            "`!ng setclub <key> <value>` - Store permanent club information\n"
            "`!ng clear` - Reset current channel's conversation memory\n"
            "`!ng status` - View RAM, Disk, and Database statistics\n\n"
            "*You can also talk to the bot directly by @mentioning it or replying to its messages!*"
        )
        await ctx.reply(text, mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(BotCommands(bot))
