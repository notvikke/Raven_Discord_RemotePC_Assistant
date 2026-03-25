# Raven - Discord Remote PC Assistant

This bot provides a bridge between Discord and high-performance AI command-line interfaces (CLIs), specifically **Gemini CLI** (v0.35.0) and **Claude Code**.

## Features
- **Default AI Chat**: Just type anything! Gemini handles any message that doesn't start with a prefix as a read-only prompt.
- `!gf <prompt>`: Full Gemini access (YOLO mode - can edit files/run commands).
- `!c <prompt>`: Interact with Claude Code CLI.
- `!g <prompt>`: Explicit Gemini prompt (Backward compatible).
## 🛠️ Prerequisites
Before running the bot, you **must** have the following CLI agents installed and authenticated on your machine:

### 1. Gemini CLI
The core engine for the default chat and file management.
- **Install**: `npm install -g @google/gemini-cli`
- **Authenticate**: Run `gemini` in your terminal and follow the login prompts.
- **Documentation**: [Gemini CLI GitHub](https://github.com/google/gemini-cli)

### 2. Claude Code
Used for the `!c` command for specialized coding tasks.
- **Install**: `npm install -g @anthropic-ai/claude-code`
- **Authenticate**: Run `claude` in your terminal to complete the one-time setup.
- **Documentation**: [Claude Code Guide](https://docs.anthropic.com/claude/docs/claude-code)

---

## Setup
1. Clone this repository.
2. Rename `.env.example` to `.env` and fill in your credentials.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the bot:
   ```bash
   python discord_bot.py
   ```

## 🎵 Music Integration (Spotify)
> **⚠️ In Development:** Spotify music control features are currently being implemented and tested. This section will be updated with full setup instructions once the feature is stable.

## 🚀 Running on Startup (Windows)
...

To have the bot start automatically when you log into your PC, you can use one of these methods:

### Method 1: The Startup Folder (Easiest)
1. Press `Win + R`, type `shell:startup`, and hit Enter.
2. Right-click the `start_bot.bat` file in your project folder and select **Create Shortcut**.
3. Drag that shortcut into the **Startup** folder you just opened.
4. Done! A console window will appear whenever you log in.

### Method 2: Task Scheduler (Stealth/Hidden)
1. Search for **Task Scheduler** in the Start menu and open it.
2. Click **Create Basic Task...** on the right.
3. Name it "Ravenn Bot" and set the Trigger to **When I log on**.
4. Set the Action to **Start a program**.
5. Browse and select your `start_bot.bat`.
6. In the **Start in (optional)** field, copy and paste the path to your project folder (e.g., `D:\Dev 2026\Fun\Ravenn`).
7. Finish. Now the bot will run in the background every time you log in.

## Dependencies
- `discord.py`
- `python-dotenv`
- Gemini CLI and Claude CLI must be installed and in your PATH.
