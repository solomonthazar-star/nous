# nous
# Discord Oracle Bot

A Discord bot that quotes religious and philosophical texts passage-by-passage. Supports:

- **Gutenberg texts**: Bhagavad Gita, Upanishads, Dhammapada (auto-download and cache)
- **API texts**: Bible (WEB/KJV), Tanakh (JPS 1917), Quran (Pickthall), Book of Mormon
- **Slash commands** for clean, numbered passages

---

## Features

- `/list_texts` → lists all available texts
- `/quote <text> <number>` → quote a specific passage
- `/random_passage [text]` → get a random passage
- `/search <query>` → search Gutenberg texts
- Auto-splits long passages for Discord message limit (2000 characters)
- Preloads all texts at startup for instant response

---

## Setup for Pella Deployment

1. **Create GitHub repo** and push the following structure:

