import os
import sys
import time
import asyncio
import logging
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands, tasks

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import DISCORD_TOKEN, BOT_PREFIX, TEMP_MEDIA_DIR
from src.utils.ai_client import ask_ai
from src.utils.cmds import send_chunked_message, is_admin_user
from src.utils.tools.web_search import search_web
from src.utils.tools.pdf_maker import create_pdf_document
from src.utils.tools.events import get_events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ignite_bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=BOT_PREFIX + " ", intents=intents, help_command=None)

@tasks.loop(minutes=30)
async def cleanup_temp_media():
    now = time.time()
    for f in TEMP_MEDIA_DIR.glob("*"):
        if f.is_file() and f.name != ".gitkeep":
            if now - f.stat().st_mtime > 900:  # 15 minutes
                try:
                    f.unlink()
                except Exception:
                    pass

@bot.event
async def on_ready():
    logger.info(f"Ignite Bot connected as {bot.user} (ID: {bot.user.id})")
    
    # Load prefix commands cog
    try:
        await bot.load_extension("src.utils.cmds")
        logger.info("Loaded prefix commands extension.")
    except Exception as e:
        logger.error(f"Failed loading cmds extension: {e}")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} application slash commands.")
    except Exception as e:
        logger.error(f"Failed syncing slash commands: {e}")

    if not cleanup_temp_media.is_running():
        cleanup_temp_media.start()

    activity = discord.Activity(type=discord.ActivityType.listening, name=f"{BOT_PREFIX} help | @mention")
    await bot.change_presence(activity=activity)

def extract_image_url(message: discord.Message) -> str | None:
    for att in message.attachments:
        if att.content_type and att.content_type.startswith("image/"):
            return att.url
        ext = att.filename.lower().split(".")[-1]
        if ext in ("png", "jpg", "jpeg", "webp", "gif"):
            return att.url
            
    # Check if user replied to an image message
    if message.reference and message.reference.resolved:
        ref_msg = message.reference.resolved
        if isinstance(ref_msg, discord.Message):
            for att in ref_msg.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    return att.url
    return None

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Check prefix command trigger
    content = message.content.strip()
    if content.startswith(BOT_PREFIX):
        await bot.process_commands(message)
        return

    # Check mention or reply trigger
    is_mentioned = bot.user in message.mentions
    is_reply_to_bot = False
    if message.reference and message.reference.resolved:
        ref_msg = message.reference.resolved
        if isinstance(ref_msg, discord.Message) and ref_msg.author.id == bot.user.id:
            is_reply_to_bot = True

    if is_mentioned or is_reply_to_bot:
        clean_text = content
        if bot.user:
            clean_text = clean_text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        if not clean_text and not message.attachments:
            clean_text = "Hello!"

        image_url = extract_image_url(message)

        async with message.channel.typing():
            res = await ask_ai(
                channel_id=message.channel.id,
                guild_id=message.guild.id if message.guild else None,
                user_id=message.author.id,
                user_name=message.author.display_name,
                prompt=clean_text,
                image_url_or_data=image_url
            )

        file_obj = None
        if res.get("pdf_path") and res["pdf_path"].exists():
            file_obj = discord.File(str(res["pdf_path"]))

        await send_chunked_message(message.channel, res["text"], reference=message, file=file_obj)

        if res.get("pdf_path") and res["pdf_path"].exists():
            try:
                res["pdf_path"].unlink()
            except Exception:
                pass

# Slash commands
@bot.tree.command(name="ask", description="Ask Ignite AI assistant anything with context memory")
async def slash_ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    res = await ask_ai(
        channel_id=interaction.channel_id,
        guild_id=interaction.guild_id,
        user_id=interaction.user.id,
        user_name=interaction.user.display_name,
        prompt=prompt
    )

    file_obj = None
    if res.get("pdf_path") and res["pdf_path"].exists():
        file_obj = discord.File(str(res["pdf_path"]))

    if len(res["text"]) <= 1900:
        await interaction.followup.send(res["text"], file=file_obj)
    else:
        # First chunk via followup, rest as channel messages
        chunks = [res["text"][i:i+1900] for i in range(0, len(res["text"]), 1900)]
        await interaction.followup.send(chunks[0], file=file_obj)
        for c in chunks[1:]:
            if interaction.channel:
                await interaction.channel.send(c)

    if res.get("pdf_path") and res["pdf_path"].exists():
        try:
            res["pdf_path"].unlink()
        except Exception:
            pass

@bot.tree.command(name="search", description="Search the web with Tavily")
async def slash_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    results = await search_web(query)
    embed = discord.Embed(title=f"Search: {query}", description=results[:4000], color=0x3498DB)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="events", description="List upcoming Ignite club events")
async def slash_events(interaction: discord.Interaction):
    guild_id = interaction.guild_id or interaction.user.id
    events = await get_events(guild_id)
    if not events:
        await interaction.response.send_message("No upcoming club events found.")
        return

    embed = discord.Embed(title="Ignite Club Events", color=0xE67E22)
    for ev in events:
        val = f"**Date:** {ev['date_time']}\n{ev.get('details', '')}"
        embed.add_field(name=f"#{ev['id']} - {ev['title']}", value=val, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pdf", description="Create and download a quick PDF document")
async def slash_pdf(interaction: discord.Interaction, title: str, content: str):
    await interaction.response.defer()
    pdf_path = await create_pdf_document(title, content)
    try:
        await interaction.followup.send(
            f"Generated PDF: **{title}**",
            file=discord.File(str(pdf_path))
        )
    finally:
        if pdf_path.exists():
            pdf_path.unlink()

def main():
    if not DISCORD_TOKEN:
        print("\n[ERROR] DISCORD_TOKEN is missing!")
        print("Please create or edit your .env file and set DISCORD_TOKEN=your_token_here\n")
        sys.exit(1)
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
