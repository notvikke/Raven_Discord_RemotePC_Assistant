# Raven - Discord Remote PC Assistant

This bot provides a bridge between Discord and high-performance AI command-line interfaces (CLIs), specifically **Gemini CLI** (v0.35.0) and **Claude Code**.

## Features
- `!g <prompt>`: Interact with Gemini in non-interactive mode.
- `!gf <prompt>`: Full tool-use mode (YOLO).
- `!c <prompt>`: Interact with Claude Code CLI.
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
Ravenn can now control your Spotify playback using the built-in Gemini AI.

### 1. Get Spotify API Keys
- Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
- Create a new app and name it "Ravenn Music".
- In the app settings, set the **Redirect URI** to `http://localhost:3000/callback`.
- Copy your **Client ID** and **Client Secret** and add them to your `.env` file.

### 2. Perform One-Time Authorization
Because this uses a browser-based OAuth flow, you need to authorize it once on your machine:
1. Open your terminal in the project folder.
2. Run this command:
   ```bash
   gemini -p "list my spotify playlists" --allowed-mcp-server-names spotify-music
   ```
3. A browser window will open. Log in and click "Authorize".
4. Once your playlists appear in the terminal, you're all set!

### 3. Use it in Discord!
Try these commands:
- `!g play some chill music on Spotify`
- `!g what song is this?`
- `!g skip this track`
- `!g search for [Artist Name] on Spotify`

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
