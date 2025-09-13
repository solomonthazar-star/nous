# bot.py
import os
import json
import random
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, List

import discord
from discord.ext import commands
from discord import app_commands

# ----------------- CONFIG -----------------
TOKEN = os.getenv("MTQxNjIxNTQ2NTc3NjM4MTk5Mw.GMKy7l.81Aq2E0InQiDOLKLvxJeW1f7Ne85WpLrQLgdMM")
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
TEXTS: Dict[str, Dict] = {}  # title -> {"type":"api/local","passages":[...]}

# ----------------- UTILITIES -----------------
def split_into_chunks(text: str, max_len: int = MAX_MESSAGE_LENGTH) -> List[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space == -1:
                space = end
            chunks.append(text[start:space].strip())
            start = space
        else:
            chunks.append(text[start:].strip())
            break
    return chunks

def format_passage(title: str, number: int, text: str) -> str:
    return f"**{title} — Passage {number}**\n{text}"

# ----------------- FETCHING FUNCTIONS -----------------
async def fetch_gutenberg(title: str, url: str) -> List[str]:
    local_file = TEXTS_DIR / f"{title.replace(' ','_')}.json"
    if local_file.exists():
        with open(local_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["passages"]
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            raw = await resp.text()
    lines = [line.strip() for line in raw.split("\n\n") if line.strip()]
    with open(local_file, "w", encoding="utf-8") as f:
        json.dump({"title": title, "passages": lines}, f, ensure_ascii=False, indent=2)
    return lines

async def fetch_api_text(title: str) -> Dict:
    async with aiohttp.ClientSession() as session:
        if title in ["World English Bible", "KJV"]:
            url = f"https://bible-api.com/Genesis"
            async with session.get(url) as resp:
                data = await resp.json()
            verses = []
            if "verses" in data:
                for v in data["verses"]:
                    verses.append(f"{v['book_name']} {v['chapter']}:{v['verse']} {v['text']}")
            return {"title": title, "passages": verses}
        elif title == "Tanakh (JPS 1917)":
            url = "https://www.sefaria.org/api/texts/Genesis.1?lang=bi"
            async with session.get(url) as resp:
                data = await resp.json()
            passages = data.get("text", [])
            return {"title": title, "passages": passages}
        elif title == "Quran (Pickthall)":
            url = "https://api.alquran.cloud/v1/surah/1/en.pickthall"
            async with session.get(url) as resp:
                data = await resp.json()
            passages = [ay['text'] for ay in data['data']['ayahs']]
            return {"title": title, "passages": passages}
        elif title == "Book of Mormon":
            url = "https://api.nephi.org/book_of_mormon/1"
            async with session.get(url) as resp:
                data = await resp.json()
            passages = [v['text'] for v in data['verses']]
            return {"title": title, "passages": passages}
    return {"title": title, "passages": []}

async def preload_all_texts():
    # Preload Gutenberg texts
    for title, url in GUTENBERG_TEXTS.items():
        passages = await fetch_gutenberg(title, url)
        TEXTS[title] = {"type": "local", "passages": passages}
        print(f"Loaded Gutenberg text: {title} ({len(passages)} passages)")

    # Preload API texts
    for title in API_TEXTS.keys():
        data = await fetch_api_text(title)
        TEXTS[title] = {"type": "api", "passages": data["passages"]}
        print(f"Loaded API text: {title} ({len(data['passages'])} passages)")

# ----------------- BOT EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        await tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Failed to sync: {e}")
    print("Preloading all texts...")
    await preload_all_texts()
    print("All texts loaded.")

# ----------------- SLASH COMMANDS -----------------
@tree.command(name="list_texts", description="List available texts")
async def list_texts(interaction: discord.Interaction):
    lines = []
    for title, info in TEXTS.items():
        lines.append(f"- {title} ({info['type']})")
    await interaction.response.send_message("\n".join(lines))

@tree.command(name="quote", description="Quote a numbered passage")
@app_commands.describe(text_title="Title of the text", number="Passage number (starting at 1)")
async def quote(interaction: discord.Interaction, text_title: str, number: int):
    if text_title not in TEXTS:
        await interaction.response.send_message(f"Text not found: {text_title}", ephemeral=True)
        return
    passages = TEXTS[text_title]["passages"]
    if number < 1 or number > len(passages):
        await interaction.response.send_message(f"Invalid passage number. {text_title} has {len(passages)} passages.", ephemeral=True)
        return
    text = passages[number-1]
    chunks = split_into_chunks(text)
    await interaction.response.defer()
    for i, chunk in enumerate(chunks, start=1):
        await interaction.followup.send(format_passage(text_title, number if len(chunks)==1 else f"{number} part {i}", chunk))

@tree.command(name="random_passage", description="Get a random passage")
@app_commands.describe(text_title="Optional: title of the text")
async def random_passage(interaction: discord.Interaction, text_title: str = None):
    await interaction.response.defer()
    if text_title:
        if text_title not in TEXTS:
            await interaction.followup.send(f"Text not found: {text_title}")
            return
        passages = TEXTS[text_title]["passages"]
        idx = random.randrange(len(passages))
        text = passages[idx]
        chunks = split_into_chunks(text)
        for i, chunk in enumerate(chunks, start=1):
            await interaction.followup.send(format_passage(text_title, idx+1 if len(chunks)==1 else f"{idx+1} part {i}", chunk))
    else:
        title = random.choice(list(TEXTS.keys()))
        passages = TEXTS[title]["passages"]
        idx = random.randrange(len(passages))
        text = passages[idx]
        chunks = split_into_chunks(text)
        for i, chunk in enumerate(chunks, start=1):
            await interaction.followup.send(format_passage(title, idx+1 if len(chunks)==1 else f"{idx+1} part {i}", chunk))

@tree.command(name="search", description="Search Gutenberg texts")
@app_commands.describe(query="Search term")
async def search(interaction: discord.Interaction, query: str):
    results = []
    for title, info in TEXTS.items():
        if info['type'] != 'local':
            continue
        passages = info['passages']
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
