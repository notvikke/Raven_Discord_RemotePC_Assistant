import discord
import os
import asyncio
import json
import re
import subprocess
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID', 0))
FULL_ACCESS = os.getenv('FULL_ACCESS', 'True').lower() == 'true'

# Executable Paths
GEMINI_PATH = r"C:\Users\vikas\AppData\Roaming\npm\gemini.cmd"
CLAUDE_PATH = r"C:\Users\vikas\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\cli.js"
USER_CONFIG_FILE = "user_config.json"

if not TOKEN:
    print("ERROR: DISCORD_TOKEN not found in .env file.")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=['!', '>'], intents=intents, help_command=None)

# --- User Configuration Management ---
def load_user_configs():
    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_config(user_id, config):
    configs = load_user_configs()
    configs[str(user_id)] = config
    with open(USER_CONFIG_FILE, 'w') as f:
        json.dump(configs, f, indent=4)

def get_user_config(user_id):
    configs = load_user_configs()
    return configs.get(str(user_id))

# --- Helper Functions ---
def is_safe_path(path):
    """
    Check if a path is safe (not a root drive, not a sensitive system directory).
    """
    path = os.path.abspath(path).lower()
    
    # Check for root drives (e.g., C:\, D:\)
    drive = os.path.splitdrive(path)[0]
    if path == drive + os.path.sep or path == drive + "/":
        return False, "You cannot set a root drive as your project path. Please provide a specific subfolder."

    # Check for sensitive system directories
    restricted = [
        r"c:\windows",
        r"c:\users",
        r"c:\program files",
        r"c:\program files (x86)",
        r"c:\users\public",
    ]
    
    for r in restricted:
        if path.startswith(r):
            return False, f"The directory `{r}` is restricted for security reasons. Please use a personal project folder."

    return True, ""

def is_allowed():
    async def predicate(ctx):
        if not ALLOWED_USER_ID: return True
        return ctx.author.id == ALLOWED_USER_ID
    return commands.check(predicate)

def clean_ansi(text):
    """Remove ANSI escape sequences from text"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

async def run_gemini_native(ctx, prompt, yolo=False):
    """
    Runs Gemini CLI in headless streaming mode with user-specific configuration.
    """
    user_id = ctx.author.id
    config = get_user_config(user_id)
    
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    # Use the user's specific session and directories
    include_dirs = config.get('allowed_dirs', "").strip()
    cwd = config.get('project_path', os.getcwd())
    session_name = f"user_{user_id}"

    # Build the command arguments list
    music_prompt = (
        "You have access to a Spotify music control tool via 'python spotify_control.py <command> [query]'. "
        "Commands: play (query), pause, skip, previous, status. "
        "Example: 'python spotify_control.py play Shape of You'. "
        "Use this tool whenever the user asks for music-related actions."
    )
    
    args = [
        GEMINI_PATH, "-p", f"{music_prompt}\n\nUser request: {prompt}",
        "--output-format", "stream-json"
    ]
    
    if include_dirs:
        args.extend(["--include-directories", include_dirs])
        
    if yolo:
        args.extend(["--approval-mode", "yolo"])
    else:
        args.extend(["--approval-mode", "plan"])

    # Safely join arguments for Windows shell execution
    cmd_str = subprocess.list2cmdline(args)

    # Start process via shell
    process = await asyncio.create_subprocess_shell(
        cmd_str,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy()
    )

    full_response = ""
    header_info = ""
    status_msg = None
    debug_log = ""

    try:
        async for line in process.stdout:
            if not line: break
            try:
                line_text = line.decode(errors='replace').strip()
                if not line_text: continue
                
                if line_text.startswith('{') and line_text.endswith('}'):
                    event = json.loads(line_text)
                    if event.get('type') == 'init':
                        header_info = f"👤 **User:** `{config['nickname']}` | **Session:** `{session_name}`\n"
                    elif event.get('type') == 'message' and event.get('role') == 'assistant':
                        full_response += event.get('content', '')
                    elif event.get('type') == 'tool_use':
                        tool_name = event.get('tool_name', 'unknown')
                        msg_text = f"🛠️ *Gemini is using tool: `{tool_name}`...*"
                        if not status_msg:
                            status_msg = await ctx.send(msg_text)
                        else:
                            await status_msg.edit(content=msg_text)
                else:
                    if not line_text.startswith('Loaded'):
                        debug_log += line_text + "\n"
            except json.JSONDecodeError:
                debug_log += line.decode(errors='replace')
                continue

        stderr_output = (await process.stderr.read()).decode(errors='replace').strip()
        await process.wait()
        
        if status_msg:
            try: await status_msg.delete()
            except: pass

        full_response = clean_ansi(full_response).strip()
        
        # Filter out common non-error stderr messages
        filtered_stderr = "\n".join([
            line for line in stderr_output.splitlines() 
            if "Loaded cached credentials" not in line and "Reading config" not in line
        ]).strip()

        if not full_response:
            if filtered_stderr:
                final_output = f"❌ **CLI Error:**\n```\n{filtered_stderr}\n```"
            elif debug_log:
                final_output = f"⚠️ **No content, showing debug logs:**\n```\n{debug_log[:1500]}\n```"
            else:
                final_output = "❌ Gemini returned no response content. This could mean the prompt didn't trigger an assistant message."
        else:
            final_output = f"{header_info}\n{full_response}" if header_info else full_response

        if len(final_output) > 1900:
            chunks = [final_output[i:i+1900] for i in range(0, len(final_output), 1900)]
            for chunk in chunks: await ctx.send(f"```\n{chunk}\n```")
        else:
            if final_output.startswith(('❌', '⚠️', '👤')):
                await ctx.send(final_output)
            else:
                await ctx.send(f"```\n{final_output}\n```")
    except Exception as e:
        await ctx.send(f"Error running Gemini CLI: {e}")

# --- Direct Spotify Commands ---
@bot.command(name='play')
@is_allowed()
async def play_command(ctx, *, query=None):
    """Directly play music on Spotify."""
    cmd = ["python", "spotify_control.py", "play"]
    if query: cmd.append(query)
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    output = stdout.decode().strip() or stderr.decode().strip()
    await ctx.send(f"🎵 {output}" if output else "🎵 Command executed.")

@bot.command(name='pause')
@is_allowed()
async def pause_command(ctx):
    """Pause Spotify playback."""
    process = await asyncio.create_subprocess_exec(
        "python", "spotify_control.py", "pause",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    await ctx.send(f"⏸️ {stdout.decode().strip()}")

@bot.command(name='skip')
@is_allowed()
async def skip_command(ctx):
    """Skip to the next track."""
    process = await asyncio.create_subprocess_exec(
        "python", "spotify_control.py", "skip",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    await ctx.send(f"⏭️ {stdout.decode().strip()}")

@bot.command(name='nowplaying')
@is_allowed()
async def nowplaying_command(ctx):
    """Show what's currently playing."""
    process = await asyncio.create_subprocess_exec(
        "python", "spotify_control.py", "status",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    await ctx.send(f"🎶 {stdout.decode().strip()}")

@bot.command(name='help')
async def help_command(ctx):
    """Displays a list of available commands and explains what the bot can do."""
    embed = discord.Embed(
        title="Ravenn Bot Help",
        description=(
            "Ravenn is a bridge between Discord and high-performance AI command-line interfaces (CLIs), "
            "it allows you to manage local files, write code, and run shell commands directly from Discord."
        ),
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🚀 Getting Started",
        value="`!setup`: Start the onboarding wizard to set your nickname and project folder.",
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI Commands",
        value=(
            "**Just type a message**: Gemini handles plain text as a read-only prompt.\n"
            "`!gf [prompt]`: Full Gemini access (YOLO mode - can edit files/run commands).\n"
            "`!c [prompt]`: Interact with Claude Code CLI.\n"
            "`!upload`: Send one or more files with this command to save them to your project."
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Configuration",
        value=(
            "`!setdirs [paths]`: Update the additional directories Gemini can access.\n"
            "`!status`: View your current profile and project configuration."
        ),
        inline=False
    )
    
    embed.set_footer(text="Tip: Use !gf only when you want the AI to make actual changes to your files.")
    await ctx.send(embed=embed)

@bot.command(name='status')
async def status_command(ctx):
    """Displays the user's current configuration."""
    user_id = ctx.author.id
    config = get_user_config(user_id)
    
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    embed = discord.Embed(
        title=f"👤 Profile Status: {config.get('nickname', 'User')}",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="📂 Project Path (CWD)",
        value=f"`{config.get('project_path', 'Not Set')}`",
        inline=False
    )
    
    allowed_dirs = config.get('allowed_dirs', 'None')
    embed.add_field(
        name="🌍 Allowed Directories",
        value=f"`{allowed_dirs if allowed_dirs else 'None'}`",
        inline=False
    )
    
    embed.add_field(
        name="🆔 Session ID",
        value=f"`user_{user_id}`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='upload')
async def upload_command(ctx):
    """Saves attachments to the user's project directory."""
    user_id = ctx.author.id
    config = get_user_config(user_id)
    
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    if not ctx.message.attachments:
        await ctx.send("❌ Please attach one or more files to your message when running `!upload`.")
        return

    project_path = config.get('project_path')
    saved_files = []

    for attachment in ctx.message.attachments:
        filename = re.sub(r'[^\w\.-]', '_', attachment.filename)
        save_path = os.path.join(project_path, filename)
        
        try:
            await attachment.save(save_path)
            saved_files.append(f"`{filename}`")
        except Exception as e:
            await ctx.send(f"❌ Error saving `{attachment.filename}`: {e}")

    if saved_files:
        files_list = ", ".join(saved_files)
        await ctx.send(f"✅ Saved {len(saved_files)} file(s) to your project: {files_list}\n"
                       f"You can now ask Gemini about them with `!g`.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check if the message starts with any of our command prefixes
    prefixes = ('!', '>')
    is_command_prefix = message.content.startswith(prefixes)
    
    user_id = str(message.author.id)
    configs = load_user_configs()
    is_setup = user_id in configs

    if is_command_prefix:
        # It's a prefixed command
        command_name = message.content[1:].split()[0].lower()
        if not is_setup and command_name not in ['setup', 'help']:
            await message.channel.send(f"👋 Hi {message.author.mention}! It looks like you haven't set up your project yet. Run `!setup` to get started, or `!help` to see what I can do.")
        await bot.process_commands(message)
    else:
        # It's a plain message - treat as Gemini prompt if user is setup
        if is_setup:
            ctx = await bot.get_context(message)
            async with ctx.channel.typing():
                await run_gemini_native(ctx, message.content, yolo=False)
        else:
            # For non-setup users, we don't respond to plain messages to avoid spam
            pass

@bot.event
async def on_ready():
    print(f'Ravenn Bot is ready. Logged in as {bot.user}')
    print(f'Allowed User ID: {ALLOWED_USER_ID}')
    print(f'Commands: !setup, !g [prompt], !gf [prompt], !c [prompt]')

@bot.command(name='setup')
async def setup_command(ctx):
    """Interactive Onboarding Wizard for users"""
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        await ctx.send("👋 **Welcome!**\nLet's set up your environment. What should I call you? (Nickname)")
        msg = await bot.wait_for('message', check=check, timeout=60)
        nickname = msg.content

        await ctx.send(f"Nice to meet you, {nickname}! 📂 **Provide the full path to your project folder.**\n(e.g., `C:\\Projects\\MyAwesomeApp`)")
        msg = await bot.wait_for('message', check=check, timeout=60)
        project_path = msg.content.strip('`').strip()

        if not os.path.isdir(project_path):
            await ctx.send(f"❌ Error: `{project_path}` is not a valid directory. Please run `!setup` again.")
            return

        is_safe, error_msg = is_safe_path(project_path)
        if not is_safe:
            await ctx.send(f"❌ {error_msg}")
            return

        await ctx.send("🌍 **Provide any other folders Gemini should have access to.** (Comma-separated, or type `none`)")
        msg = await bot.wait_for('message', check=check, timeout=60)
        allowed_dirs = "" if msg.content.lower() == 'none' else msg.content.strip('`').strip()

        user_config = {
            "nickname": nickname,
            "project_path": project_path,
            "allowed_dirs": allowed_dirs
        }
        save_user_config(ctx.author.id, user_config)

        await ctx.send(f"✅ **Setup Complete!**\nYour project path is set to `{project_path}`.\nYou can now use `!g` or `!gf` to interact with Gemini.")

    except asyncio.TimeoutError:
        await ctx.send("⏰ Setup timed out. Please try again with `!setup`.")

@bot.command(name='setdirs')
async def setdirs_command(ctx, *, dirs):
    """Update allowed directories for the user"""
    user_id = ctx.author.id
    config = get_user_config(user_id)
    
    if not config:
        await ctx.send("❌ You haven't set up your profile yet! Use `!setup` to get started.")
        return

    allowed_dirs = "" if dirs.lower() == 'none' else dirs.strip('`').strip()
    
    if allowed_dirs:
        for d in allowed_dirs.split(','):
            d = d.strip()
            if not os.path.isdir(d):
                await ctx.send(f"❌ Error: `{d}` is not a valid directory.")
                return
            is_safe, error_msg = is_safe_path(d)
            if not is_safe:
                await ctx.send(f"❌ {error_msg}")
                return

    config['allowed_dirs'] = allowed_dirs
    save_user_config(user_id, config)
    
    await ctx.send(f"✅ **Allowed directories updated!**\nGemini now has access to: `{allowed_dirs if allowed_dirs else 'None'}`")

@bot.command(name='c')
@is_allowed()
async def claude_command(ctx, *, prompt):
    """Runs a prompt through the local Claude CLI"""
    async with ctx.channel.typing():
        try:
            cmd = ["node", CLAUDE_PATH, "-p", prompt]
            if FULL_ACCESS:
                cmd.extend(["--dangerously-skip-permissions", "--add-dir", "C:\\", "D:\\"])

            cmd_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd)
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()
            )
            stdout, stderr = await process.communicate()
            output = (stdout.decode(errors='replace') + stderr.decode(errors='replace')).strip()
            output = clean_ansi(output)

            if not output: output = "Claude returned no output."

            if len(output) > 1900:
                await ctx.send(f"```\n{output[:1900]}\n```")
                await ctx.send("... (Truncated due to length)")
            else:
                await ctx.send(f"```\n{output}\n```")
        except Exception as e:
            await ctx.send(f"Error running Claude Code: {e}")

@bot.command(name='g')
@is_allowed()
async def gemini_command(ctx, *, prompt):
    """Runs Gemini CLI in native mode (read-only)"""
    async with ctx.channel.typing():
        await run_gemini_native(ctx, prompt, yolo=False)

@bot.command(name='gf')
@is_allowed()
async def gemini_full_command(ctx, *, prompt):
    """Runs Gemini CLI in native mode with full access (auto-approve all)"""
    async with ctx.channel.typing():
        await run_gemini_native(ctx, prompt, yolo=True)

if __name__ == "__main__":
    bot.run(TOKEN)
