# Ravenn Bot: Project Analysis & Report

This report provides a comprehensive overview of the Ravenn Discord Bot, its architecture, setup requirements, and potential for future growth.

---

## 1. What is the app doing?
Ravenn is a **bridge application** that connects the Discord interface to high-performance AI command-line interfaces (CLIs), specifically **Gemini CLI** and **Claude Code**.

- **Autonomous Assistance:** It allows users to prompt powerful AI agents that have direct access to the local file system and shell.
- **Project Isolation:** It manages individual user "workspaces," ensuring that AI actions (like file reading or code generation) are confined to specific, user-defined project directories.
- **Safety Modes:** It implements two levels of Gemini interaction:
    - **Read-Only (Plan Mode):** The AI can analyze but not modify.
    - **Full Access (YOLO Mode):** The AI can autonomously edit files and run commands.
- **Persistent Memory:** It uses session management to ensure the AI remembers context across multiple messages within a specific Discord user session.

---

## 2. How is it working?
The bot is built using **Python** and the **discord.py** library. Its core logic follows an asynchronous, event-driven pattern:

- **Subprocess Execution:** When a command like `!g` or `!gf` is issued, the bot spawns a headless shell subprocess (via `asyncio.create_subprocess_shell`). It executes the `gemini.cmd` executable with specific flags (`--output-format stream-json`).
- **Real-Time Stream Parsing:** The bot "listens" to the JSON stream emitted by the Gemini CLI. It parses events like `init` (metadata), `message` (content chunks), and `tool_use` (activity indicators) to provide immediate feedback in Discord.
- **Dynamic Configuration:**
    - **`user_config.json`:** A local persistent database storing user profiles (nicknames, project paths, and allowed directories).
    - **`cwd` Management:** The bot dynamically sets the *Current Working Directory* of the AI subprocess to the user's specific project path.
- **ANSI Sanitization:** It includes a regex-based cleaner to remove terminal escape sequences, ensuring the AI's output looks clean in Discord's markdown blocks.

---

## 3. Fresh Setup: Initial Knowledge & Steps

### Prerequisites
- **Python 3.8+** installed.
- **Node.js** installed (required for Gemini/Claude CLIs).
- **Gemini CLI** and **Claude Code CLI** installed globally via npm.
- **Discord Bot Token:** Created via the [Discord Developer Portal](https://discord.com/developers/applications).

### Step-by-Step Setup
1. **Environment Config:**
    - Rename `.env.example` to `.env`.
    - Fill in `DISCORD_TOKEN` and your own Discord ID in `ALLOWED_USER_ID`.
2. **Virtual Environment:**
    - Run `python -m venv bot-env`.
    - Activate it and run `pip install -r requirements.txt`.
3. **Bot Authorization:**
    - Ensure the bot has `Message Content Intent` enabled in the Developer Portal.
    - Invite the bot with `Send Messages` and `Embed Links` permissions.
4. **First Run:**
    - Start the bot using `start_bot.bat` or `python discord_bot.py`.
    - **Crucial:** In Discord, run `!setup` immediately. Without this, AI commands will be disabled for your account.

---

## 4. Future Enhancements (Roadmap)

To take Ravenn from a powerful tool to a production-grade service, consider these additions:

### A. Security & Guardrails
- **Path Sandboxing:** Implement a check to prevent users from setting `C:\` or `C:\Windows` as their project folder.
- **Rate Limiting:** Prevent users from spamming long-running AI tasks that could consume system resources or API quota.

### B. User Experience
- **File Upload Support:** Allow users to upload a file to Discord and have the bot automatically move it to their project directory for the AI to analyze.
- **Image Support:** Enable Gemini's multimodal capabilities by allowing the bot to process images sent in Discord.
- **Dashboard Command:** A `!status` command to show current project path, session length, and token usage statistics.

### C. Advanced Features
- **Git Integration:** A command to have the AI automatically commit and push changes to a GitHub repo after a successful `!gf` task.
- **MCP Server Support:** Integrate with [Model Context Protocol](https://modelcontextprotocol.io/) servers to give the AI access to even more tools (Google Search, Databases, etc.).
- **Voice-to-Task:** Integrate with Discord voice channels to allow "hands-free" coding via speech-to-text.
