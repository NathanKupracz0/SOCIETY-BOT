import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import json
import datetime
from datetime import datetime, timedelta
import time
import asyncio

# Load environment variables from .env file
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Set up logging
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- DATA STORAGE ---
todo_lists = {}


TODO_FILE = "todo_data.json"
def load_todos():
    if not os.path.exists(TODO_FILE):
        return {}
    with open(TODO_FILE, "r") as f:
        return json.load(f)

def save_todos(data):
    with open(TODO_FILE, "w") as f:
        json.dump(data, f, indent=4)
        
        todo_lists = {}

REMINDER_FILE = "reminders_data.json"
def load_reminders():
    if not os.path.exists(REMINDER_FILE):
        return {}
    with open(REMINDER_FILE, "r") as f:
        return json.load(f)

def save_reminders(data):
    with open(REMINDER_FILE, "w") as f:
        json.dump(data, f, indent=4)
        
LOG_FILE = "chatdat.json"

def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        return json.load(f)

def save_logs(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def add_log(entry):
    logs = load_logs()
    logs.append(entry)
    save_logs(logs)
        

        
        

# Load data on startup


# ---Committee Checker---

def is_committee_member(member: discord.Member) -> bool:
    """Return True if member has the committee role."""
    committee_role_name = "systems administrator"
    for role in member.roles:
        if role.name.lower() == committee_role_name.lower():  # case-insensitive
            return True
    return False

@bot.check
async def global_committee_check(ctx):
    # Allow these commands for everyone
    allowed_for_all = ["ping", "help"]
    if ctx.command.name in allowed_for_all:
        return True

    # Require committee role for all other commands
    if is_committee_member(ctx.author):
        return True
    else:
        await ctx.send("🚫 You do not have permission to use this command.")
        return False
   
# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- COMMANDS ---
@bot.command(name="todo+")
async def todo_add(ctx, *, task):
    cid = str(ctx.channel.id)

    if cid not in todo_lists:
        todo_lists[cid] = {"tasks": []}

    todo_lists[cid]["tasks"].append({"task": task, "assigned_to": None})
    save_todos(todo_lists)
    
    await ctx.send(f"➕ Added task: **{task}**")

@bot.command(name="todo-")
async def todo_remove(ctx, index: int):
    data = load_todos()
    cid = str(ctx.channel.id)

    if cid not in data or index < 1 or index > len(data[cid]["tasks"]):
        return await ctx.send("❌ Invalid task number.")

    removed = data[cid]["tasks"].pop(index - 1)
    save_todos(data)

    await ctx.send(f"🗑 Removed task: **{removed['task']}**")

@bot.command()
async def todoview(ctx):
    data = load_todos()
    cid = str(ctx.channel.id)

    if cid not in data or not data[cid]["tasks"]:
        return await ctx.send("📭 No tasks in this channel/thread.")

    msg = "**📋 To-do list for this channel/thread:**\n\n"
    for i, t in enumerate(data[cid]["tasks"], start=1):
        assigned = f"<@{t['assigned_to']}>" if t["assigned_to"] else "None"
        msg += f"{i}. **{t['task']}** — Assigned: {assigned}\n"

    await ctx.send(msg)

@bot.command()
async def todoassign(ctx, index: int, user: discord.Member):
    data = load_todos()
    cid = str(ctx.channel.id)

    if cid not in data or index < 1 or index > len(data[cid]["tasks"]):
        return await ctx.send("❌ Invalid task number.")

    data[cid]["tasks"][index - 1]["assigned_to"] = user.id
    save_todos(data)

    await ctx.send(f"👤 Assigned **{user.mention}** to task #{index}.")

@bot.command()
async def todounassign(ctx, index: int):
    data = load_todos()
    cid = str(ctx.channel.id)

    if cid not in data or index < 1 or index > len(data[cid]["tasks"]):
        return await ctx.send("❌ Invalid task number.")

    # Unassign the task
    data[cid]["tasks"][index - 1]["assigned_to"] = None

    save_todos(data)
    await ctx.send("Task unassigned successfully.")

    
@bot.command()
async def todoviewall(ctx):
    data = load_todos()

    if not data:
        return await ctx.send("📭 No to-do lists exist yet.")

    msg = "**📂 All channels/threads with to-do lists:**\n\n"

    for cid, content in data.items():
        channel = bot.get_channel(int(cid))
        if channel:
            msg += f"• {channel.mention} — {len(content['tasks'])} tasks\n"
        else:
            msg += f"• Unknown channel ({cid}) — {len(content['tasks'])} tasks\n"

    await ctx.send(msg)

@bot.command()
async def todofinish(ctx):
    data = load_todos()
    cid = str(ctx.channel.id)

    if cid not in data:
        return await ctx.send("❌ This channel/thread has no to-do list.")

    del data[cid]
    save_todos(data)

    await ctx.send("✅ This channel/thread's to-do list has been cleared.")

bot.run(token)

#reminders!!!! yay

@bot.command()
async def remind(ctx, role: discord.Role, date: str, time: str, channel: discord.TextChannel, *, message: str):
    
    await ctx.send(f"""
Role: {role.mention}
Date: {date}
Time: {time}
Channel: {channel.mention}
Message: {message}
""")
    
    
#log

async def get_log_channel(guild):
    channel = discord.utils.get(guild.text_channels, name="soc-logs")
    if channel:
        return channel

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    for role in guild.roles:
        if role.permissions.administrator or role.permissions.manage_guild:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True)

    channel = await guild.create_text_channel(
        name="soc-logs",
        overwrites=overwrites,
        reason="Private server log channel"
    )

    return channel
# Log helper (JSON + Discord)

async def log_event(guild, entry, message_text):
    add_log(entry)
    log_channel = await get_log_channel(guild)
    await log_channel.send(message_text)

# Message logging
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    entry = {
        "type": "message",
        "author": str(message.author),
        "author_id": message.author.id,
        "content": message.content,
        "channel": message.channel.name,
        "channel_id": message.channel.id,
        "timestamp": datetime.utcnow().isoformat()
    }

    log_text = (
        f"📝 **Message Sent**\n"
        f"User: {message.author}\n"
        f"Channel: {message.channel.mention}\n"
        f"Content: {message.content}"
    )

    await log_event(message.guild, entry, log_text)
    await bot.process_commands(message)

# Command Logging
@bot.event
async def on_command(ctx):
    entry = {
        "type": "command",
        "author": str(ctx.author),
        "author_id": ctx.author.id,
        "command": ctx.command.qualified_name,
        "message": ctx.message.content,
        "channel": ctx.channel.name,
        "timestamp": datetime.utcnow().isoformat()
    }

    log_text = (
        f"⚙️ **Command Used**\n"
        f"User: {ctx.author}\n"
        f"Channel: {ctx.channel.mention}\n"
        f"Command: `{ctx.message.content}`"
    )

    await log_event(ctx.guild, entry, log_text)
    
    # Message Deletion
    
    @bot.event
    async def on_message_delete(message):
        if message.author.bot:
            return

        entry = {
        "type": "message_delete",
        "original_author": str(message.author),
        "original_author_id": message.author.id,
        "content": message.content,
        "channel": message.channel.name,
        "timestamp": datetime.utcnow().isoformat()
    }

        log_text = (
        f"🗑️ **Message Deleted**\n"
        f"Author: {message.author}\n"
        f"Channel: {message.channel.mention}\n"
        f"Content: {message.content}"
    )

        await log_event(message.guild, entry, log_text)


    







