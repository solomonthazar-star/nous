# bot.py
import os
import json
import random
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, List, Tuple

import discord
from discord.ext import commands
from discord import app_commands

# ----------------- CONFIG -----------------
TOKEN = os.getenv("DISCORD_TOKEN")
TEXTS_DIR = Path("texts")
TEXTS_DIR.mkdir(exist_ok=True)
COMMAND_PREFIX = "!"
MAX_MESSAGE_LENGTH = 2000  # Discord limit
# Gutenberg text URLs (public domain)
GUTENBERG_TEXTS = {
    "Bhagavad Gita": "https://www.gutenberg.org/files/2388/2388-0.txt",
    "Upanishads": "https://www.gutenberg.org/files/23455/23455-0.txt",
    "Dhammapada": "https://www.gutenberg.org/files/159/159-0.txt"
}
# API-based texts
API_TEXTS = {
    "World English Bible": "bible-api",
    "KJV": "bible-api",
    "Tanakh (JPS 1917)": "sefaria",
    "Quran (Pickthall)": "alquran",
    "Book of Mormon": "nephi"
}

# ----------------- BOT SETUP -----------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
tree = bot.tree

# ----------------- DATA STRUCTURES -----------------
# title -> {"type":"api/local","source":...,"passages":[...]}
TEXTS: Dict[str, Dict] = {}

# ----------------- UTILITIES -----------------
def split_into_chunks(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split long text into chunks <= max_len without breaking words."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        if end < len(text):
            # Try to split at last space before max_len
            space = text.rfind(" ", start, end)
            if space == -1:
                space = end
            chunks.append(text[start:space].strip())
            start = space
        else:
            chunks.append(text[start:].strip())
            break
    return chunks

async def fetch_gutenberg(title: str, url: str) -> List[str]:
    """Download Gutenberg text and split into numbered passages."""
    local_file = TEXTS_DIR / f"{title.replace(' ','_')}.json"
    if local_file.exists():
        with open(local_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["passages"]
    # Fetch online
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            raw = await resp.text()
    # Basic cleaning: split by double newline or linebreaks
    lines = [line.strip() for line in raw.split("\n\n") if line.strip()]
    # Save locally
    with open(local_file, "w", encoding="utf-8") as f:
        json.dump({"title": title, "passages": lines}, f, ensure_ascii=False, indent=2)
    return lines

async def fetch_api_text(title: str) -> Dict:
    """Fetch API text data. Returns a dict: {'title':..., 'passages':[...]}"""
    if title in ["World English Bible", "KJV"]:
        # Example: fetch entire Genesis for demo
        url = f"https://bible-api.com/Genesis"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        # Build passages list (verse by verse)
        verses = []
        if "verses" in data:
            for v in data["verses"]:
                verses.append(f"{v['book_name']} {v['chapter']}:{v['verse']} {v['text']}")
        return {"title": title, "passages": verses}
    elif title == "Tanakh (JPS 1917)":
        # Example: Genesis 1
        url = "https://www.sefaria.org/api/texts/Genesis.1?lang=bi"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        passages = data.get("text", [])
        return {"title": title, "passages": passages}
    elif title == "Quran (Pickthall)":
        url = "https://api.alquran.cloud/v1/surah/1/en.pickthall"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        passages = [ay['text'] for ay in data['data']['ayahs']]
        return {"title": title, "passages": passages}
    elif title == "Book of Mormon":
        url = "https://api.nephi.org/book_of_mormon/1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        passages = [v['text'] for v in data['verses']]
        return {"title": title, "passages": passages}
    return {"title": title, "passages": []}

def format_passage(title: str, number: int, text: str) -> str:
    return f"**{title} — Passage {number}**\n{text}"

async def get_passages(title: str) -> List[str]:
    """Get passages, either API or Gutenberg/local."""
    title_key = title.strip()
    if title_key in TEXTS:
        return TEXTS[title_key]["passages"]
    # Determine source
    if title_key in GUTENBERG_TEXTS:
        passages = await fetch_gutenberg(title_key, GUTENBERG_TEXTS[title_key])
        TEXTS[title_key] = {"type":"local","passages":passages}
        return passages
    elif title_key in API_TEXTS:
        passages = await fetch_api_text(title_key)
        TEXTS[title_key] = {"type":"api","passages":passages["passages"]}
        return passages["passages"]
    else:
        return []

# ----------------- BOT EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        await tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Failed to sync: {e}")

# ----------------- SLASH COMMANDS -----------------
@tree.command(name="list_texts", description="List available texts")
async def list_texts(interaction: discord.Interaction):
    lines = []
    # Local Gutenberg
    for title in GUTENBERG_TEXTS.keys():
        lines.append(f"- {title} (local / Gutenberg)")
    # API texts
    for title in API_TEXTS.keys():
        lines.append(f"- {title} (API)")
    await interaction.response.send_message("\n".join(lines))

@tree.command(name="quote", description="Quote a numbered passage")
@app_commands.describe(text_title="Title of the text", number="Passage number (starting at 1)")
async def quote(interaction: discord.Interaction, text_title: str, number: int):
    passages = await get_passages(text_title)
    if not passages:
        await interaction.response.send_message(f"Text not found: {text_title}", ephemeral=True)
        return
    if number < 1 or number > len(passages):
        await interaction.response.send_message(f"Invalid passage number. {text_title} has {len(passages)} passages.", ephemeral=True)
        return
    text = passages[number-1]
    chunks = split_into_chunks(text)
    for i, chunk in enumerate(chunks, start=1):
        await interaction.followup.send(format_passage(text_title, number if len(chunks)==1 else f"{number} part {i}", chunk))

@tree.command(name="random_passage", description="Get a random passage")
@app_commands.describe(text_title="Optional: title of the text")
async def random_passage(interaction: discord.Interaction, text_title: str = None):
    if text_title:
        passages = await get_passages(text_title)
        if not passages:
            await interaction.response.send_message(f"Text not found: {text_title}", ephemeral=True)
            return
        idx = random.randrange(len(passages))
        text = passages[idx]
        chunks = split_into_chunks(text)
        for i, chunk in enumerate(chunks, start=1):
            await interaction.followup.send(format_passage(text_title, idx+1 if len(chunks)==1 else f"{idx+1} part {i}", chunk))
    else:
        # Pick random text
        all_titles = list(GUTENBERG_TEXTS.keys()) + list(API_TEXTS.keys())
        title = random.choice(all_titles)
        passages = await get_passages(title)
        idx = random.randrange(len(passages))
        text = passages[idx]
        chunks = split_into_chunks(text)
        for i, chunk in enumerate(chunks, start=1):
            await interaction.followup.send(format_passage(title, idx+1 if len(chunks)==1 else f"{idx+1} part {i}", chunk))

@tree.command(name="search", description="Search local Gutenberg texts")
@app_commands.describe(query="Search term")
async def search(interaction: discord.Interaction, query: str):
    results = []
    for title in GUTENBERG_TEXTS.keys():
        passages = await get_passages(title)
        for i, p in enumerate(passages, start=1):
            if query.lower() in p.lower():
                snippet = p[:300].rsplit(" ",1)[0] + ("..." if len(p)>300 else "")
                results.append(f"**{title} — Passage {i}**\n{snippet}")
                if len(results) >= 5:
                    break
        if len(results) >=5:
            break
    if results:
        await interaction.response.send_message("\n\n".join(results))
    else:
        await interaction.response.send_message("No matches found.", ephemeral=True)

# ----------------- RUN -----------------
if __name__ == "__main__":
    if not TOKEN:
        print("Please set DISCORD_TOKEN environment variable.")
    else:
        bot.run(TOKEN)
