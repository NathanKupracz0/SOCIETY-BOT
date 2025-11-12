import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Set up logging
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, log_handler=logging)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - {bot.user.id}')
    print('------')

bot.run(token,  log_handler=handler, log_level=logging.DEBUG)

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name='general')
    if channel:
        await channel.send(f'Welcome to the server, {member.mention}!')

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong!')



