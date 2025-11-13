import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import json

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
TODO_DATA_FILE = "todo_data.json"

def save_todo_data():
    """Save todo_lists to JSON file."""
    with open(TODO_DATA_FILE, "w") as f:
        json.dump(todo_lists, f, indent=4)

def load_todo_data():
    """Load todo_lists from JSON file."""
    global todo_lists
    try:
        with open(TODO_DATA_FILE, "r") as f:
            todo_lists = json.load(f)
    except FileNotFoundError:
        todo_lists = {}

# Load data on startup
load_todo_data()

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

@bot.command(name="todoview")
async def tdview(ctx):
    """View the current to-do list."""
    guild_id = str(ctx.guild.id)
    todo = todo_lists.get(guild_id, {"tasks": [], "assigned_user": None})
    tasks = todo["tasks"]
    assigned_user = todo["assigned_user"]

    if not tasks:
        await ctx.send("📝 The to-do list is currently empty!")
        return

    formatted_tasks = "\n".join([f"{i+1}. {task}" for i, task in enumerate(tasks)])

    if assigned_user:
        user = await bot.fetch_user(assigned_user)
        assigned_str = f"👤 Assigned to: {user.mention}"
    else:
        assigned_str = "👤 No one is assigned yet."

    await ctx.send(f"**📋 To-Do List:**\n{formatted_tasks}\n\n{assigned_str}")


@bot.command(name="todo+")
async def td_add(ctx, *, task: str = None):
    """Add a task to the to-do list."""
    if not task:
        await ctx.send("⚠️ Please include a task to add. Example: `!todo+ finish report`")
        return

    guild_id = str(ctx.guild.id)
    if guild_id not in todo_lists:
        todo_lists[guild_id] = {"tasks": [], "assigned_user": None}

    todo_lists[guild_id]["tasks"].append(task)
    save_todo_data()
    await ctx.send(f"✅ Added task: **{task}**")


@bot.command(name="todo-")
async def td_remove(ctx, index: int = None):
    """Remove a task from the to-do list by its number."""
    guild_id = str(ctx.guild.id)
    todo = todo_lists.get(guild_id)

    if not todo or not todo["tasks"]:
        await ctx.send("⚠️ The to-do list is empty!")
        return

    if index is None or index < 1 or index > len(todo["tasks"]):
        await ctx.send("⚠️ Please provide a valid task number. Example: `!todo- 2`")
        return

    removed_task = todo["tasks"].pop(index - 1)
    save_todo_data()
    await ctx.send(f"🗑️ Removed task: **{removed_task}**")


@bot.command(name="todoassign")
async def td_assign(ctx, user: discord.Member = None):
    """Assign the to-do list to a user."""
    guild_id = str(ctx.guild.id)
    if guild_id not in todo_lists:
        todo_lists[guild_id] = {"tasks": [], "assigned_user": None}

    if not user:
        await ctx.send("⚠️ Please mention a user to assign. Example: `!todoassign @username`")
        return

    todo_lists[guild_id]["assigned_user"] = user.id
    save_todo_data()
    await ctx.send(f"✅ To-do list assigned to {user.mention}")


bot.run(token)






