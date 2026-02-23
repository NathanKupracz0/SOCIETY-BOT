import discord
from discord.ext import commands
import os
import logging
import json
from datetime import datetime, timedelta, timezone
import asyncio
from pathlib import Path

# ================== ENV ==================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ================== FILE PATHS ==================
TODO_FILE = DATA_DIR / "todo_data.json"
REMINDER_FILE = DATA_DIR / "reminders_data.json"
COUNTDOWN_FILE = DATA_DIR / "countdowns.json"
LOG_FILE = DATA_DIR / "discord.log"

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
logger = logging.getLogger("discord")
logger.addHandler(file_handler)

# ================== BOT ==================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# ================== JSON HELPERS ==================
def load_json(path, default):
    if not path.exists():
        return default
    try:
        text = path.read_text().strip()
        if not text:
            return default
        return json.loads(text)
    except json.JSONDecodeError:
        return default

def save_json(path, data):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
    tmp.replace(path)

# ================== PERMISSIONS ==================
def is_committee_member(member):
    return any(role.name.lower() == "systems administrator" for role in member.roles)

@bot.check
async def committee_check(ctx):
    if ctx.command is None:
        return False
    root = ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name
    if root in ["remind", "commands", "ping"]:
        return True
    if is_committee_member(ctx.author):
        return True
    await ctx.send("You do not have permission.")
    return False

# ================== LOG CHANNEL ==================
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
    return await guild.create_text_channel("soc-logs", overwrites=overwrites)

# ================== TODO COMMANDS ==================
@bot.group(name="todo", invoke_without_command=True)
async def todo(ctx):
    await ctx.send("Usage: !todo add | remove | view | clear | assign | unassign | assigned")

@todo.command(name="add")
async def todo_add(ctx, *, task):
    data = load_json(TODO_FILE, {})
    cid = str(ctx.channel.id)
    data.setdefault(cid, {"tasks": []})
    data[cid]["tasks"].append({"task": task, "assigned_to": None})
    save_json(TODO_FILE, data)
    await ctx.send("Task added.")

@todo.command(name="remove")
async def todo_remove(ctx, number: int):
    data = load_json(TODO_FILE, {})
    cid = str(ctx.channel.id)
    if cid not in data or number < 1 or number > len(data[cid]["tasks"]):
        return await ctx.send("Invalid task number.")
    task = data[cid]["tasks"].pop(number - 1)
    save_json(TODO_FILE, data)
    await ctx.send(f"Removed: {task['task']}")

@todo.command(name="view")
async def todo_view(ctx):
    data = load_json(TODO_FILE, {})
    cid = str(ctx.channel.id)
    if cid not in data or not data[cid]["tasks"]:
        return await ctx.send("No tasks in this channel.")
    lines = ["To-do list:"]
    for i, t in enumerate(data[cid]["tasks"], 1):
        assigned = f"<@{t['assigned_to']}>" if t["assigned_to"] else "None"
        lines.append(f"{i}. {t['task']} — Assigned: {assigned}")
    await ctx.send("\n".join(lines))

@todo.command(name="assign")
async def todo_assign(ctx, member: discord.Member, number: int):
    data = load_json(TODO_FILE, {})
    cid = str(ctx.channel.id)
    if cid not in data or number < 1 or number > len(data[cid]["tasks"]):
        return await ctx.send("Invalid task number.")
    data[cid]["tasks"][number - 1]["assigned_to"] = member.id
    save_json(TODO_FILE, data)
    await ctx.send("Task assigned.")

@todo.command(name="unassign")
async def todo_unassign(ctx, number: int):
    data = load_json(TODO_FILE, {})
    cid = str(ctx.channel.id)
    if cid not in data or number < 1 or number > len(data[cid]["tasks"]):
        return await ctx.send("Invalid task number.")
    data[cid]["tasks"][number - 1]["assigned_to"] = None
    save_json(TODO_FILE, data)
    await ctx.send("Task unassigned.")

@todo.command(name="clear")
async def todo_clear(ctx):
    data = load_json(TODO_FILE, {})
    data.pop(str(ctx.channel.id), None)
    save_json(TODO_FILE, data)
    await ctx.send("All tasks cleared.")

@todo.command(name="assigned")
async def todo_assigned(ctx, member: discord.Member):
    data = load_json(TODO_FILE, {})
    results = []
    for cid, payload in data.items():
        for i, task in enumerate(payload.get("tasks", []), 1):
            if task.get("assigned_to") == member.id:
                channel = ctx.guild.get_channel(int(cid))
                cname = channel.mention if channel else f"(Channel {cid})"
                results.append(f"{cname}: {i}. {task['task']}")
    if not results:
        return await ctx.send(f"No tasks assigned to {member.mention}.")
    await ctx.send(f"Tasks assigned to {member.mention}:\n" + "\n".join(results))

# ================== TIME HELPERS ==================
def parse_hhmm(time_str):
    if len(time_str) != 4 or not time_str.isdigit():
        raise ValueError
    h, m = int(time_str[:2]), int(time_str[2:])
    if h > 23 or m > 59:
        raise ValueError
    return h, m

def next_from_hhmm(time_str):
    h, m = parse_hhmm(time_str)
    now = datetime.now(timezone.utc)
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t <= now:
        t += timedelta(days=1)
    return t

def advance_repeat(dt, mode):
    return {
        "day": dt + timedelta(days=1),
        "week": dt + timedelta(weeks=1),
        "month": dt + timedelta(days=30)
    }.get(mode)

# ================== REMINDERS ==================
@bot.group(name="remind", invoke_without_command=True)
async def remind(ctx):
    await ctx.send("Usage: !remind set | list | forget")

@remind.command(name="set")
async def remind_set(ctx, time: str, repeat: str = None, *, message: str = ""):
    try:
        fire = next_from_hhmm(time)
    except ValueError:
        return await ctx.send("Time must be HHMM.")
    reminders = load_json(REMINDER_FILE, [])
    reminders.append({
        "user_id": ctx.author.id,
        "channel_id": ctx.channel.id,
        "message": message,
        "time": fire.isoformat(),
        "repeat": repeat
    })
    save_json(REMINDER_FILE, reminders)
    await ctx.send("Reminder set.")

@remind.command(name="list")
async def remind_list(ctx):
    reminders = load_json(REMINDER_FILE, [])
    mine = [r for r in reminders if r["user_id"] == ctx.author.id]
    if not mine:
        return await ctx.send("No reminders.")
    now = datetime.now(timezone.utc)
    lines = ["Your reminders:"]
    for i, r in enumerate(mine, 1):
        fire = datetime.fromisoformat(r["time"])
        delta = fire - now
        lines.append(f"{i}. {r['message']} — in {int(delta.total_seconds()//60)} min")
    await ctx.send("\n".join(lines))

@remind.command(name="forget")
async def remind_forget(ctx, number: int):
    reminders = load_json(REMINDER_FILE, [])
    mine = [r for r in reminders if r["user_id"] == ctx.author.id]
    if number < 1 or number > len(mine):
        return await ctx.send("Invalid number.")
    reminders.remove(mine[number - 1])
    save_json(REMINDER_FILE, reminders)
    await ctx.send("Reminder deleted.")

# ================== COMMAND LIST ==================
@bot.command(name="commands")
async def commands_list(ctx):
    lines = [
        "Commands:",
        "",
        "Todo:",
        "!todo add <task>",
        "!todo remove <number>",
        "!todo view",
        "!todo clear",
        "!todo assign @user <number>",
        "!todo unassign <number>",
        "!todo assigned @user",
        "",
        "Reminders:",
        "!remind set <HHMM> [day|week|month] <message>",
        "!remind list",
        "!remind forget <number>",
    ]
    await ctx.send("\n".join(lines))

# ================== BACKGROUND TASK ==================
async def reminder_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        reminders = load_json(REMINDER_FILE, [])
        now = datetime.now(timezone.utc)
        keep = []
        for r in reminders:
            fire = datetime.fromisoformat(r["time"])
            if now >= fire:
                channel = bot.get_channel(r["channel_id"])
                user = bot.get_user(r["user_id"])
                if channel and user:
                    await channel.send(f"{user.mention} Reminder: {r['message']}")
                if r["repeat"]:
                    r["time"] = advance_repeat(fire, r["repeat"]).isoformat()
                    keep.append(r)
            else:
                keep.append(r)
        save_json(REMINDER_FILE, keep)
        await asyncio.sleep(30)

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    bot.loop.create_task(reminder_loop())

bot.run(TOKEN)
