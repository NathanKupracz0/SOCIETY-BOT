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
# ================== COMMAND LIST ==================
# ================== COMMAND LIST ==================
@bot.command(name="commands")
async def commands_list(ctx):
    lines = [
        "Available commands:",
        "",
        "Reminders:",
        "!remind set <HHMM> <message>",
        "!remind set <HHMM> day|week|month <message>",
        "!remind list",
        "!remind forget <number>",
        "",
        "Countdowns:",
        "!countdown set <YYYY-MM-DD> <HHMM> <label>",
        "!countdown list",
        "!countdown forget <number>",
        "",
        "Todo:",
        "!todo view",
        "!todo assigned @user"
    ]
    if is_committee_member(ctx.author):
        lines += [
            "",
            "Admin commands:",
            "",
            "Todo management:",
            "!todo add <task>",
            "!todo remove <number>",
            "!todo clear",
            "!todo assign @user <number>",
            "!todo unassign <number>",
            "",
            "Admin reminders:",
            "!remind set @user <HHMM> #channel [day|week|month] <message>",
            "!remind set @role <HHMM> #channel [day|week|month] <message>",
            "",
            "Admin countdowns:",
            "!countdown set @user <YYYY-MM-DD> <HHMM> #channel <label>",
            "!countdown set @role <YYYY-MM-DD> <HHMM> #channel <label>"
        ]
    await ctx.send("\n".join(lines))

# ================== TODO COMMANDS ==================
@bot.group(name="todo", invoke_without_command=True)
async def todo(ctx):
    await ctx.send("Usage: !todo add | remove | view | clear | assign | unassign")

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
    removed = data[cid]["tasks"].pop(number - 1)
    save_json(TODO_FILE, data)
    await ctx.send("Task removed: " + removed["task"])

@todo.command(name="view")
async def todo_view(ctx):
    data = load_json(TODO_FILE, {})
    cid = str(ctx.channel.id)
    if cid not in data or not data[cid]["tasks"]:
        return await ctx.send("No tasks in this channel.")
    lines = ["To-do list:"]
    for i, t in enumerate(data[cid]["tasks"], 1):
        assigned = f"<@{t['assigned_to']}>" if t["assigned_to"] else "None"
        lines.append(f"{i}. {t['task']} — Assigned to: {assigned}")
    await ctx.send("\n".join(lines))
    
@todo.command(name="assigned")
async def todo_assigned(ctx, member: discord.Member):
    data = load_json(TODO_FILE, {})
    results = []

    for cid, payload in data.items():
        for i, task in enumerate(payload.get("tasks", []), 1):
            if task.get("assigned_to") == member.id:
                channel = ctx.guild.get_channel(int(cid))
                channel_name = channel.mention if channel else f"(Channel {cid})"
                results.append(f"{channel_name}: {i}. {task['task']}")

    if not results:
        return await ctx.send(f"No tasks assigned to {member.mention}.")

    await ctx.send(
        f"Tasks assigned to {member.mention}:\n" + "\n".join(results)
    )

@todo.command(name="clear")
async def todo_clear(ctx):
    data = load_json(TODO_FILE, {})
    cid = str(ctx.channel.id)
    data.pop(cid, None)
    save_json(TODO_FILE, data)
    await ctx.send("All tasks cleared.")

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

# ================== TIME HELPERS ==================
def parse_hhmm(time_str: str):
    if len(time_str) != 4 or not time_str.isdigit():
        raise ValueError
    h, m = int(time_str[:2]), int(time_str[2:])
    if h > 23 or m > 59:
        raise ValueError
    return h, m

def next_from_hhmm(time_str: str):
    h, m = parse_hhmm(time_str)
    now = datetime.now(timezone.utc)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target

def resolve_channel(ctx, token, is_admin):
    if token is None:
        return ctx.channel
    if not is_admin:
        raise PermissionError
    if not token.startswith("<#"):
        raise ValueError
    cid = int(token.strip("<#>"))
    channel = ctx.guild.get_channel(cid)
    if not channel:
        raise ValueError
    return channel

def advance_repeat(dt, mode):
    if mode == "day":
        return dt + timedelta(days=1)
    if mode == "week":
        return dt + timedelta(weeks=1)
    if mode == "month":
        return dt + timedelta(days=30)
    return None

# ================== COUNTDOWN MILESTONES ==================
COUNTDOWN_MILESTONES = [
    ("7d", 7 * 86400, "7 days remaining"),
    ("3d", 3 * 86400, "3 days remaining"),
    ("24h", 86400, "24 hours remaining"),
    ("12h", 43200, "12 hours remaining"),
    ("1h", 3600, "1 hour remaining"),
    ("now", 0, "Deadline reached")
]

# ================== REMIND COMMANDS ==================
@bot.group(name="remind", invoke_without_command=True)
async def remind(ctx):
    await ctx.send("Usage: !remind set | list | forget")

@remind.command(name="set")
async def remind_set(ctx, target: str, time: str = None, channel_ref: str = None,
                     repeat: str = None, *, message: str = None):
    is_admin = is_committee_member(ctx.author)
    if target.startswith("<@"):
        if not is_admin:
            return await ctx.send("You can only remind yourself.")
        if target.startswith("<@&"):
            role = ctx.guild.get_role(int(target[3:-1]))
            users = role.members if role else []
        else:
            member = ctx.guild.get_member(int(target.strip("<@!>")))
            users = [member] if member else []
        if not (time and message):
            return await ctx.send("Time and message required.")
        time_str = time
    else:
        users = [ctx.author]
        time_str = target
        message = message or ""
        repeat = channel_ref
        channel_ref = None
    try:
        channel = resolve_channel(ctx, channel_ref, is_admin)
    except Exception:
        return await ctx.send("Invalid channel or permissions.")
    try:
        remind_time = next_from_hhmm(time_str)
    except ValueError:
        return await ctx.send("Time must be HHMM.")
    reminders = load_json(REMINDER_FILE, [])
    for u in users:
        reminders.append({
            "user_id": u.id,
            "channel_id": channel.id,
            "message": message,
            "time": remind_time.isoformat(),
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
        h = int(delta.total_seconds() // 3600)
        m = int(delta.total_seconds() % 3600 // 60)
        lines.append(f"{i}. {r['message']} — in {h}h {m}m")
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

# ================== BACKGROUND TASKS ==================
async def reminder_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        reminders = load_json(REMINDER_FILE, [])
        now = datetime.now(timezone.utc)
        remaining = []
        for r in reminders:
            fire = datetime.fromisoformat(r["time"])
            if now >= fire:
                channel = bot.get_channel(r["channel_id"])
                user = bot.get_user(r["user_id"])
                if channel and user:
                    await channel.send(f"{user.mention} Reminder: {r['message']}")
                if r["repeat"]:
                    r["time"] = advance_repeat(fire, r["repeat"]).isoformat()
                    remaining.append(r)
            else:
                remaining.append(r)
        save_json(REMINDER_FILE, remaining)
        await asyncio.sleep(30)

async def countdown_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        countdowns = load_json(COUNTDOWN_FILE, [])
        now = datetime.now(timezone.utc)
        changed = False
        for c in countdowns:
            deadline = datetime.fromisoformat(c["deadline"])
            remaining = (deadline - now).total_seconds()
            fired = set(c.get("fired", []))
            for key, sec, label in COUNTDOWN_MILESTONES:
                if remaining <= sec and key not in fired:
                    channel = bot.get_channel(c["channel_id"])
                    user = bot.get_user(c["user_id"])
                    if channel and user:
                        await channel.send(f"{user.mention} ⏳ **{label}** — {c['label']}")
                    fired.add(key)
                    changed = True
            c["fired"] = list(fired)
        if changed:
            save_json(COUNTDOWN_FILE, countdowns)
        await asyncio.sleep(60)

# ================== MESSAGE LOGGING ==================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.attachments:
        log_channel = await get_log_channel(message.guild)
        links = "\n".join(a.url for a in message.attachments)
        await log_channel.send(
            f"Message from {message.author} in {message.channel.mention}:\n"
            f"{message.content or '[No text]'}\nAttachments:\n{links}"
        )
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    log_channel = await get_log_channel(before.guild)
    await log_channel.send(
        f"Message edited by {before.author}:\n"
        f"Before: {before.content}\nAfter: {after.content}"
    )

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_channel = await get_log_channel(message.guild)
    await log_channel.send(
        f"Message deleted by {message.author}:\n{message.content}"
    )

@bot.event
async def on_command(ctx):
    if ctx.author.bot:
        return
    log_channel = await get_log_channel(ctx.guild)
    await log_channel.send(f"Command used: {ctx.message.content}")

# ================== READY ==================
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    bot.loop.create_task(reminder_loop())
    bot.loop.create_task(countdown_loop())

bot.run(TOKEN)