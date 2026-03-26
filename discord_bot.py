import asyncio
import json
import os
import re
import shutil
import sys
from typing import Optional, Tuple

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", 0))
FULL_ACCESS = os.getenv("FULL_ACCESS", "True").lower() == "true"
USER_CONFIG_FILE = "user_config.json"


def resolve_executable(
    env_var_name: str, known_paths: list[str], path_candidates: list[str]
) -> str:
    """
    Resolve executable in this order:
    1) explicit env var
    2) known Windows paths
    3) PATH candidates
    """
    env_value = os.getenv(env_var_name, "").strip()
    if env_value:
        env_value = os.path.abspath(os.path.normpath(env_value.strip('"')))
        if os.path.exists(env_value):
            return env_value
        raise RuntimeError(
            f"{env_var_name} is set but does not exist: {env_value}. "
            "Update .env with a valid path."
        )

    for path in known_paths:
        if os.path.exists(path):
            return path

    for candidate in path_candidates:
        found = shutil.which(candidate)
        if found:
            return found

    raise RuntimeError(
        f"Could not resolve executable for {env_var_name}. "
        f"Set {env_var_name} in .env or install one of: {', '.join(path_candidates)}"
    )


def resolve_claude_invocation() -> list[str]:
    """
    Resolve Claude invocation in this order:
    1) CLAUDE_PATH env var (JS path or executable)
    2) known JS path
    3) claude on PATH
    """
    env_value = os.getenv("CLAUDE_PATH", "").strip()
    if env_value:
        env_value = os.path.abspath(os.path.normpath(env_value.strip('"')))
        if not os.path.exists(env_value):
            raise RuntimeError(
                f"CLAUDE_PATH is set but does not exist: {env_value}. "
                "Update .env with a valid path."
            )
        if env_value.lower().endswith(".js"):
            return ["node", env_value]
        return [env_value]

    known_js_path = (
        r"C:\Users\vikas\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\cli.js"
    )
    if os.path.exists(known_js_path):
        return ["node", known_js_path]

    claude_exec = shutil.which("claude") or shutil.which("claude.cmd")
    if claude_exec:
        return [claude_exec]

    raise RuntimeError(
        "Could not resolve Claude CLI. Set CLAUDE_PATH in .env to either "
        "the claude executable path or Claude cli.js path."
    )


def build_gemini_exec_args(prompt: str, include_dirs: str, yolo: bool) -> list[str]:
    args = [GEMINI_PATH, "-p", prompt, "--output-format", "stream-json"]

    if include_dirs:
        args.extend(["--include-directories", include_dirs])

    args.extend(["--approval-mode", "yolo" if yolo else "plan"])

    # .cmd/.bat need cmd /c on Windows when not using shell=True
    if GEMINI_PATH.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", *args]
    return args


try:
    GEMINI_PATH = resolve_executable(
        env_var_name="GEMINI_PATH",
        known_paths=[
            r"C:\Users\vikas\AppData\Roaming\npm\gemini.cmd",
            r"C:\Program Files\nodejs\gemini.cmd",
        ],
        path_candidates=["gemini", "gemini.cmd"],
    )
    CLAUDE_INVOCATION = resolve_claude_invocation()
except RuntimeError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

if not TOKEN:
    print("ERROR: DISCORD_TOKEN not found in .env file.")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=["!", ">"], intents=intents, help_command=None)


# --- User Configuration Management ---
def load_user_configs() -> dict:
    if not os.path.exists(USER_CONFIG_FILE):
        return {}

    try:
        with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_user_config(user_id: int, config: dict) -> None:
    configs = load_user_configs()
    configs[str(user_id)] = config
    with open(USER_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=4)


def normalize_path_text(path: str) -> str:
    cleaned = str(path).strip().strip("`").strip('"')
    return os.path.abspath(os.path.normpath(cleaned))


def normalize_allowed_dirs_string(raw: str) -> str:
    raw = str(raw or "").strip()
    if not raw:
        return ""

    normalized: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        normalized.append(normalize_path_text(part))
    return ",".join(normalized)


def normalize_user_config(config: dict) -> Optional[dict]:
    if not isinstance(config, dict):
        return None

    nickname = str(config.get("nickname", "User")).strip() or "User"
    project_path_raw = config.get("project_path")
    if not project_path_raw:
        return None

    project_path = normalize_path_text(project_path_raw)
    allowed_dirs = normalize_allowed_dirs_string(config.get("allowed_dirs", ""))

    normalized = dict(config)
    normalized["nickname"] = nickname
    normalized["project_path"] = project_path
    normalized["allowed_dirs"] = allowed_dirs
    return normalized


def get_user_config(user_id: int) -> Optional[dict]:
    configs = load_user_configs()
    raw_config = configs.get(str(user_id))
    return normalize_user_config(raw_config) if raw_config else None


# --- Helper Functions ---
def is_safe_path(path: str) -> Tuple[bool, str]:
    """
    Check if a path is safe (not a root drive, not a sensitive system directory).
    """
    path = normalize_path_text(path).lower()

    drive = os.path.splitdrive(path)[0]
    if path == drive + os.path.sep or path == drive + "/":
        return (
            False,
            "You cannot set a root drive as your project path. Please provide a specific subfolder.",
        )

    restricted = [
        r"c:\windows",
        r"c:\users",
        r"c:\program files",
        r"c:\program files (x86)",
        r"c:\users\public",
    ]
    for restricted_path in restricted:
        if path.startswith(restricted_path):
            return (
                False,
                f"The directory `{restricted_path}` is restricted for security reasons. "
                "Please use a personal project folder.",
            )

    return True, ""


def validate_directory(path: str) -> Tuple[Optional[str], Optional[str]]:
    normalized = normalize_path_text(path)
    if not os.path.isdir(normalized):
        return None, f"`{normalized}` is not a valid directory."

    is_safe, error_msg = is_safe_path(normalized)
    if not is_safe:
        return None, error_msg

    return normalized, None


def parse_and_validate_allowed_dirs(raw_input: str) -> Tuple[Optional[str], Optional[str]]:
    raw_input = str(raw_input or "").strip()
    if not raw_input or raw_input.lower() == "none":
        return "", None

    normalized_dirs: list[str] = []
    for path in raw_input.split(","):
        path = path.strip()
        if not path:
            continue

        normalized, error = validate_directory(path)
        if error:
            return None, error
        normalized_dirs.append(normalized)

    return ",".join(normalized_dirs), None


def is_authorized_user(user_id: int) -> bool:
    if not ALLOWED_USER_ID:
        return True
    return user_id == ALLOWED_USER_ID


def is_allowed():
    async def predicate(ctx):
        return is_authorized_user(ctx.author.id)

    return commands.check(predicate)


def clean_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def filter_cli_stderr(stderr_output: str) -> str:
    ignore_patterns = [
        "Loaded cached credentials",
        "Reading config",
        "Checking for updates",
    ]
    return "\n".join(
        line for line in stderr_output.splitlines() if not any(p in line for p in ignore_patterns)
    ).strip()


def unauthorized_message() -> str:
    return "🚫 You are not authorized to use this Ravenn instance."


async def ensure_authorized_for_ctx(ctx) -> bool:
    if is_authorized_user(ctx.author.id):
        return True
    await ctx.send(unauthorized_message())
    return False


async def run_gemini_native(ctx, prompt: str, yolo: bool = False):
    """
    Runs Gemini CLI in headless streaming mode with user-specific configuration.
    """
    if not await ensure_authorized_for_ctx(ctx):
        return

    user_id = ctx.author.id
    config = get_user_config(user_id)
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    include_dirs = config.get("allowed_dirs", "").strip()
    cwd = config.get("project_path", os.getcwd())
    session_name = f"user_{user_id}"

    if not os.path.isdir(cwd):
        await ctx.send(
            f"❌ Your configured project path no longer exists: `{cwd}`. "
            "Please run `!setup` again."
        )
        return

    process = await asyncio.create_subprocess_exec(
        *build_gemini_exec_args(prompt, include_dirs, yolo),
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )

    full_response = ""
    header_info = ""
    status_msg = None
    last_tool = None

    try:
        assert process.stdout is not None
        async for line in process.stdout:
            if not line:
                break
            try:
                line_text = line.decode(errors="replace").strip()
                if not line_text:
                    continue

                if line_text.startswith("{") and line_text.endswith("}"):
                    event = json.loads(line_text)
                    if event.get("type") == "init":
                        header_info = (
                            f"👤 **User:** `{config['nickname']}` | **Session:** `{session_name}`\n"
                        )
                    elif event.get("type") == "message" and event.get("role") == "assistant":
                        full_response += event.get("content", "")
                    elif event.get("type") == "tool_use":
                        last_tool = event.get("tool_name", "unknown")
                        msg_text = f"🛠️ *Gemini is using tool: `{last_tool}`...*"
                        if not status_msg:
                            status_msg = await ctx.send(msg_text)
                        else:
                            await status_msg.edit(content=msg_text)
            except json.JSONDecodeError:
                continue

        stderr_bytes = await process.stderr.read() if process.stderr else b""
        await process.wait()
        exit_code = process.returncode

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        full_response = clean_ansi(full_response).strip()
        filtered_stderr = filter_cli_stderr(stderr_bytes.decode(errors="replace").strip())

        if not full_response:
            if filtered_stderr:
                final_output = (
                    f"❌ **Gemini CLI Error (exit code {exit_code}):**\n"
                    f"```\n{filtered_stderr}\n```"
                )
            elif exit_code and exit_code != 0:
                final_output = f"❌ Gemini CLI exited with code `{exit_code}` and no output."
            elif last_tool:
                final_output = (
                    f"{header_info}\n✅ Action completed using tool: `{last_tool}`"
                    if header_info
                    else f"✅ Action completed using tool: `{last_tool}`"
                )
            else:
                final_output = f"{header_info}\n✅ Done." if header_info else "✅ Done."
        else:
            suffix = ""
            if filtered_stderr:
                suffix = f"\n\n[stderr]\n{filtered_stderr}"
            final_output = f"{header_info}\n{full_response}{suffix}" if header_info else full_response

        if len(final_output) > 1900:
            chunks = [final_output[i : i + 1900] for i in range(0, len(final_output), 1900)]
            for chunk in chunks:
                await ctx.send(f"```\n{chunk}\n```")
        else:
            if final_output.startswith(("❌", "⚠️", "👤")):
                await ctx.send(final_output)
            else:
                await ctx.send(f"```\n{final_output}\n```")
    except Exception as e:
        await ctx.send(f"Error running Gemini CLI: {e}")


async def run_spotify_script(command: str, query: Optional[str] = None) -> str:
    cmd = [sys.executable, "spotify_control.py", command]
    if query:
        cmd.append(query)

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    output = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()

    if process.returncode != 0:
        return f"Spotify command failed (exit code {process.returncode}): {err or output or 'Unknown error'}"
    return output or err or "Command executed."


class SetupCancelled(Exception):
    pass


async def prompt_setup_input(ctx, check, prompt_text: str, timeout: int = 120) -> str:
    await ctx.send(prompt_text)
    msg = await bot.wait_for("message", check=check, timeout=timeout)
    content = msg.content.strip()
    if content.lower() in {"cancel", "!cancel"}:
        raise SetupCancelled
    return content


# --- Direct Spotify Commands ---
@bot.command(name="play")
@is_allowed()
async def play_command(ctx, *, query=None):
    """Directly play music on Spotify."""
    output = await run_spotify_script("play", query=query)
    await ctx.send(f"🎵 {output}")


@bot.command(name="pause")
@is_allowed()
async def pause_command(ctx):
    """Pause Spotify playback."""
    output = await run_spotify_script("pause")
    await ctx.send(f"⏸️ {output}")


@bot.command(name="skip")
@is_allowed()
async def skip_command(ctx):
    """Skip to the next track."""
    output = await run_spotify_script("skip")
    await ctx.send(f"⏭️ {output}")


@bot.command(name="nowplaying")
@is_allowed()
async def nowplaying_command(ctx):
    """Show what's currently playing."""
    output = await run_spotify_script("status")
    await ctx.send(f"🎶 {output}")


@bot.command(name="help")
async def help_command(ctx):
    """Displays a list of available commands and explains what the bot can do."""
    is_authorized = is_authorized_user(ctx.author.id)
    config = get_user_config(ctx.author.id)

    embed = discord.Embed(
        title="Ravenn Bot Help",
        description=(
            "Ravenn is your remote assistant for coding, project files, and Spotify control."
        ),
        color=discord.Color.blue(),
    )

    if not is_authorized:
        embed.add_field(
            name="Access",
            value=(
                "This bot is currently locked to the owner account (`ALLOWED_USER_ID`). "
                "You can still view this help, but command execution is restricted."
            ),
            inline=False,
        )
    elif not config:
        embed.add_field(
            name="Start Here (First-Time Setup)",
            value=(
                "1. Run `!setup`\n"
                "2. Choose nickname + project folder\n"
                "3. Type a normal message to chat with Gemini in safe mode"
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="You're Ready",
            value=(
                f"Profile: `{config.get('nickname', 'User')}`\n"
                f"Project: `{config.get('project_path', 'Not set')}`\n"
                "Type a normal message to start a safe Gemini chat."
            ),
            inline=False,
        )

    embed.add_field(
        name="AI Modes",
        value=(
            "`plain message`: Gemini safe mode (read/plan)\n"
            "`!g [prompt]`: explicit Gemini safe mode\n"
            "`!gf [prompt]`: Gemini full mode (can edit/run)\n"
            "`!c [prompt]`: Claude Code CLI"
        ),
        inline=False,
    )

    embed.add_field(
        name="Project & Files",
        value=(
            "`!setup`: onboarding wizard\n"
            "`!upload` + file attachment(s): save files to your project\n"
            "`!setdirs [comma,separated,paths]`: add extra allowed directories\n"
            "`!status`: view current profile and directories"
        ),
        inline=False,
    )

    embed.add_field(
        name="🎵 Music Control (Spotify)",
        value=(
            "`!play [query]`: Search and play a song, artist, or album.\n"
            "`!pause`: Pause current playback.\n"
            "`!skip`: Skip to the next track.\n"
            "`!nowplaying`: Show details of the current song."
        ),
        inline=False,
    )

    embed.add_field(
        name="Quick Examples",
        value=(
            "`!g summarize this repository`\n"
            "`!gf create a Flask API in app.py`\n"
            "`!c review this codebase for security issues`"
        ),
        inline=False,
    )

    if FULL_ACCESS:
        embed.add_field(
            name="⚠️ Security Warning",
            value=(
                "`FULL_ACCESS=True` is enabled. Commands in full mode may operate with broad "
                "filesystem permissions (`C:\\` and `D:\\`). Use only in private, trusted servers."
            ),
            inline=False,
        )

    embed.set_footer(
        text="Tip: During !setup, type 'cancel' anytime to exit. Use !status to confirm your active workspace."
    )
    await ctx.send(embed=embed)


@bot.command(name="status")
async def status_command(ctx):
    """Displays the user's current configuration."""
    config = get_user_config(ctx.author.id)
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    embed = discord.Embed(
        title=f"👤 Profile Status: {config.get('nickname', 'User')}",
        color=discord.Color.green(),
    )

    embed.add_field(
        name="📂 Project Path (CWD)",
        value=f"`{config.get('project_path', 'Not Set')}`",
        inline=False,
    )

    allowed_dirs = config.get("allowed_dirs", "None")
    embed.add_field(
        name="🌍 Allowed Directories",
        value=f"`{allowed_dirs if allowed_dirs else 'None'}`",
        inline=False,
    )

    embed.add_field(name="🆔 Session ID", value=f"`user_{ctx.author.id}`", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="upload")
async def upload_command(ctx):
    """Saves attachments to the user's project directory."""
    if not await ensure_authorized_for_ctx(ctx):
        return

    config = get_user_config(ctx.author.id)
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    if not ctx.message.attachments:
        await ctx.send("❌ Please attach one or more files to your message when running `!upload`.")
        return

    project_path = config.get("project_path")
    if not project_path or not os.path.isdir(project_path):
        await ctx.send(
            "❌ Your configured project path is invalid. "
            "Please run `!setup` again to update it."
        )
        return

    saved_files = []
    for attachment in ctx.message.attachments:
        filename = re.sub(r"[^\w\.-]", "_", attachment.filename)
        save_path = os.path.join(project_path, filename)
        try:
            await attachment.save(save_path)
            saved_files.append(f"`{filename}`")
        except Exception as e:
            await ctx.send(f"❌ Error saving `{attachment.filename}`: {e}")

    if saved_files:
        files_list = ", ".join(saved_files)
        await ctx.send(
            f"✅ Saved {len(saved_files)} file(s) to your project: {files_list}\n"
            "You can now ask Gemini about them with `!g`."
        )


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    prefixes = ("!", ">")
    is_command_prefix = message.content.startswith(prefixes)

    user_id = str(message.author.id)
    configs = load_user_configs()
    is_setup = user_id in configs
    is_authorized = is_authorized_user(message.author.id)

    if is_command_prefix:
        command_parts = message.content[1:].split()
        command_name = command_parts[0].lower() if command_parts else ""
        if not is_setup and command_name not in ["setup", "help"]:
            await message.channel.send(
                f"👋 Hi {message.author.mention}! It looks like you haven't set up your project yet. "
                "Run `!setup` to get started, or `!help` to see what I can do."
            )
        await bot.process_commands(message)
        return

    # Plain message -> Gemini safe mode only if setup + authorized.
    if not is_setup:
        return

    if not is_authorized:
        await message.channel.send(unauthorized_message())
        return

    ctx = await bot.get_context(message)
    async with ctx.channel.typing():
        await run_gemini_native(ctx, message.content, yolo=False)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(unauthorized_message())
        return
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


@bot.event
async def on_ready():
    print(f"Ravenn Bot is ready. Logged in as {bot.user}")
    print(f"Allowed User ID: {ALLOWED_USER_ID}")
    print("Commands: !setup, !g [prompt], !gf [prompt], !c [prompt]")
    print(f"Gemini path: {GEMINI_PATH}")
    print(f"Claude invocation: {' '.join(CLAUDE_INVOCATION)}")
    if FULL_ACCESS:
        print(
            "WARNING: FULL_ACCESS=True. Claude full-mode commands can run with wide directory scope "
            "(C:\\ and D:\\). Use only in a private trusted environment."
        )


@bot.command(name="setup")
async def setup_command(ctx):
    """Interactive Onboarding Wizard for users"""
    if not await ensure_authorized_for_ctx(ctx):
        return

    existing = get_user_config(ctx.author.id)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        intro = discord.Embed(
            title="Setup Wizard",
            description=(
                "Let's configure your Ravenn workspace.\n"
                "Type `cancel` anytime to abort setup."
            ),
            color=discord.Color.blurple(),
        )
        intro.add_field(
            name="Step 1/3",
            value="Choose a nickname (or type `skip` to keep existing).",
            inline=False,
        )
        intro.add_field(
            name="Step 2/3",
            value="Choose your project directory (current working folder for AI tasks).",
            inline=False,
        )
        intro.add_field(
            name="Step 3/3",
            value="Optional: add extra allowed directories (comma-separated) or `none`.",
            inline=False,
        )
        await ctx.send(embed=intro)

        existing_nickname = existing.get("nickname", "User") if existing else "User"
        existing_project_path = existing.get("project_path", "") if existing else ""
        existing_allowed_dirs = existing.get("allowed_dirs", "") if existing else ""

        # Step 1: nickname
        while True:
            nickname_input = await prompt_setup_input(
                ctx,
                check,
                (
                    "👤 **Step 1/3 - Nickname**\n"
                    f"Current: `{existing_nickname}`\n"
                    "Enter a nickname, or type `skip` to keep current."
                ),
            )
            if nickname_input.lower() == "skip":
                nickname = existing_nickname
                break
            nickname = nickname_input.strip()
            if nickname:
                break
            await ctx.send("❌ Nickname cannot be empty. Try again.")

        # Step 2: project path with retry
        project_path = None
        for attempt in range(1, 4):
            project_prompt = (
                "📂 **Step 2/3 - Project Path**\n"
                f"Current: `{existing_project_path or 'Not set'}`\n"
                "Provide the full path to your project folder.\n"
                "Example: `C:\\Projects\\MyAwesomeApp`\n"
                "Type `skip` to keep current path."
            )
            project_input = await prompt_setup_input(ctx, check, project_prompt)
            if project_input.lower() == "skip" and existing_project_path:
                project_path = existing_project_path
                break

            normalized, error = validate_directory(project_input)
            if not error:
                project_path = normalized
                break

            if attempt < 3:
                await ctx.send(f"❌ {error}\nPlease try again ({attempt}/3).")
            else:
                await ctx.send(f"❌ {error}\nSetup cancelled after 3 failed attempts.")
                return

        if not project_path:
            await ctx.send("❌ Project path is required. Run `!setup` again.")
            return

        # Step 3: allowed dirs with retry
        allowed_dirs = ""
        for attempt in range(1, 4):
            dirs_prompt = (
                "🌍 **Step 3/3 - Extra Allowed Directories**\n"
                f"Current: `{existing_allowed_dirs or 'None'}`\n"
                "Enter comma-separated folders, `none` to clear, or `skip` to keep current."
            )
            dirs_input = await prompt_setup_input(ctx, check, dirs_prompt)
            if dirs_input.lower() == "skip":
                allowed_dirs = existing_allowed_dirs
                break

            parsed_dirs, dir_error = parse_and_validate_allowed_dirs(dirs_input)
            if not dir_error:
                allowed_dirs = parsed_dirs if parsed_dirs is not None else ""
                break

            if attempt < 3:
                await ctx.send(f"❌ {dir_error}\nPlease try again ({attempt}/3).")
            else:
                await ctx.send(f"❌ {dir_error}\nSetup cancelled after 3 failed attempts.")
                return

        user_config = {
            "nickname": nickname,
            "project_path": project_path,
            "allowed_dirs": allowed_dirs,
        }
        save_user_config(ctx.author.id, user_config)

        done = discord.Embed(title="✅ Setup Complete", color=discord.Color.green())
        done.add_field(name="Nickname", value=f"`{nickname}`", inline=False)
        done.add_field(name="Project Path", value=f"`{project_path}`", inline=False)
        done.add_field(
            name="Allowed Directories",
            value=f"`{allowed_dirs if allowed_dirs else 'None'}`",
            inline=False,
        )
        done.add_field(
            name="Try This Next",
            value=(
                "1. Send a normal message for safe Gemini chat\n"
                "2. Use `!g [prompt]` for explicit safe mode\n"
                "3. Use `!gf [prompt]` for full agentic mode"
            ),
            inline=False,
        )
        await ctx.send(embed=done)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Setup timed out. Run `!setup` again when you're ready.")
    except SetupCancelled:
        await ctx.send("🛑 Setup cancelled. Your existing configuration was not changed.")


@bot.command(name="setdirs")
async def setdirs_command(ctx, *, dirs):
    """Update allowed directories for the user"""
    if not await ensure_authorized_for_ctx(ctx):
        return

    config = get_user_config(ctx.author.id)
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    allowed_dirs, error = parse_and_validate_allowed_dirs(dirs)
    if error:
        await ctx.send(f"❌ Error: {error}")
        return

    config["allowed_dirs"] = allowed_dirs
    save_user_config(ctx.author.id, config)
    await ctx.send(
        "✅ **Allowed directories updated!**\n"
        f"Gemini now has access to: `{allowed_dirs if allowed_dirs else 'None'}`"
    )


@bot.command(name="c")
@is_allowed()
async def claude_command(ctx, *, prompt):
    """Runs a prompt through the local Claude CLI"""
    async with ctx.channel.typing():
        try:
            cmd = [*CLAUDE_INVOCATION, "-p", prompt]
            if FULL_ACCESS:
                cmd.extend(["--dangerously-skip-permissions", "--add-dir", "C:\\", "D:\\"])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )
            stdout, stderr = await process.communicate()
            exit_code = process.returncode

            output = clean_ansi(stdout.decode(errors="replace").strip())
            filtered_stderr = clean_ansi(filter_cli_stderr(stderr.decode(errors="replace").strip()))

            if exit_code != 0:
                body = filtered_stderr or output or "No error output."
                await ctx.send(
                    f"❌ **Claude CLI Error (exit code {exit_code}):**\n"
                    f"```\n{body}\n```"
                )
                return

            final_output = output or filtered_stderr or "Claude returned no output."
            if len(final_output) > 1900:
                await ctx.send(f"```\n{final_output[:1900]}\n```")
                await ctx.send("... (Truncated due to length)")
            else:
                await ctx.send(f"```\n{final_output}\n```")
        except Exception as e:
            await ctx.send(f"Error running Claude Code: {e}")


@bot.command(name="g")
@is_allowed()
async def gemini_command(ctx, *, prompt):
    """Runs Gemini CLI in native mode (read-only)"""
    async with ctx.channel.typing():
        await run_gemini_native(ctx, prompt, yolo=False)


@bot.command(name="gf")
@is_allowed()
async def gemini_full_command(ctx, *, prompt):
    """Runs Gemini CLI in native mode with full access (auto-approve all)"""
    async with ctx.channel.typing():
        await run_gemini_native(ctx, prompt, yolo=True)


if __name__ == "__main__":
    bot.run(TOKEN)
