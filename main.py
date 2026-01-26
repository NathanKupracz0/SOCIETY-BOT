import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import json
from datetime import datetime, timedelta
import asyncio

# ================== ENV ==================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ================== LOGGING ==================
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
logger = logging.getLogger("discord")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

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

# ================== FILES ==================
TODO_FILE = "todo_data.json"
REMINDER_FILE = "reminders_data.json"

# ================== JSON HELPERS ==================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            text = f.read().strip()
            if not text:
                return default
            return json.loads(text)
    except json.JSONDecodeError:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

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

# ================== TODO COMMAND GROUP ==================
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

# ================== REMIND COMMAND GROUP ==================
@bot.group(name="remind", invoke_without_command=True)
async def remind(ctx):
    await ctx.send("Usage: !remind set | list | forget")

@remind.command(name="set")
async def remind_set(ctx, target: str, time: str = None, *, message=None):
    is_admin = is_committee_member(ctx.author)

    if not target.startswith("<@"):
        users = [ctx.author]
        time_str = target
    else:
        if not is_admin:
            return await ctx.send("You can only remind yourself.")

        if target.startswith("<@&"):
            role_id = int(target[3:-1])
            role = ctx.guild.get_role(role_id)
            if not role:
                return await ctx.send("Role not found.")
            users = role.members
        else:
            user_id = int(target.strip("<@!>"))
            member = ctx.guild.get_member(user_id)
            if not member:
                return await ctx.send("User not found.")
            users = [member]

        if not time or not message:
            return await ctx.send("Time and message required.")
        time_str = time

    units = {"s": 1, "m": 60, "h": 3600}
    try:
        amount = int(time_str[:-1])
        unit = time_str[-1]
        seconds = amount * units[unit]
    except:
        return await ctx.send("Invalid time format.")

    remind_time = datetime.utcnow() + timedelta(seconds=seconds)
    reminders = load_json(REMINDER_FILE, [])

    for user in users:
        reminders.append({
            "user_id": user.id,
            "channel_id": ctx.channel.id,
            "message": message,
            "time": remind_time.isoformat()
        })

    save_json(REMINDER_FILE, reminders)
    await ctx.send("Reminder set.")

@remind.command(name="list")
async def remind_list(ctx):
    reminders = load_json(REMINDER_FILE, [])
    user_reminders = [r for r in reminders if r["user_id"] == ctx.author.id]

    if not user_reminders:
        return await ctx.send("No pending reminders.")

    lines = ["Your reminders:"]
    now = datetime.utcnow()

    for i, r in enumerate(user_reminders, 1):
        delta = datetime.fromisoformat(r["time"]) - now
        mins = int(delta.total_seconds() // 60)
        secs = int(delta.total_seconds() % 60)
        lines.append(f"{i}. {r['message']} — in {mins}m {secs}s")

    await ctx.send("\n".join(lines))

@remind.command(name="forget")
async def remind_forget(ctx, number: int):
    reminders = load_json(REMINDER_FILE, [])
    mine = [r for r in reminders if r["user_id"] == ctx.author.id]

    if number < 1 or number > len(mine):
        return await ctx.send("Invalid reminder number.")

    reminders.remove(mine[number - 1])
    save_json(REMINDER_FILE, reminders)
    await ctx.send("Reminder deleted.")

# ================== COMMAND LIST ==================
@bot.command(name="commands")
async def commands_list(ctx):
    lines = [
        "Available commands:",
        "",
        "Reminders:",
        "!remind set <time> <message>",
        "!remind list",
        "!remind forget <number>"
    ]

    if is_committee_member(ctx.author):
        lines += [
            "",
            "Admin commands:",
            "!todo add <task>",
            "!todo remove <number>",
            "!todo view",
            "!todo clear",
            "!todo assign @user <number>",
            "!todo unassign <number>",
            "!remind set @user <time> <message>",
            "!remind set @role <time> <message>"
        ]

    await ctx.send("\n".join(lines))

# ================== REMINDER LOOP ==================
async def reminder_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        reminders = load_json(REMINDER_FILE, [])
        now = datetime.utcnow()
        remaining = []

        for r in reminders:
            if now >= datetime.fromisoformat(r["time"]):
                channel = bot.get_channel(r["channel_id"])
                user = bot.get_user(r["user_id"])
                if channel and user:
                    await channel.send(f"{user.mention} Reminder: {r['message']}")
            else:
                remaining.append(r)

        if remaining != reminders:
            save_json(REMINDER_FILE, remaining)

        await asyncio.sleep(30)

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
            f"{message.content}\nAttachments:\n{links}"
        )

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_channel = await get_log_channel(message.guild)
    await log_channel.send(
        f"Message deleted by {message.author} in {message.channel.mention}:\n"
        f"{message.content}"
    )

# ================== READY ==================
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    bot.loop.create_task(reminder_loop())

bot.run(TOKEN)
    
