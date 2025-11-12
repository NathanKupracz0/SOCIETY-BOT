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

@bot.event
async def on_member_join(member):
    await member.send(f'Welcome to the server, {member.name}!')

@bot.command
async def on_message(message):
    if message.author == bot.user:
        return
    
    if "ping" in message.content.lower():
        await message.channel.send(f"{message.author.mention} Pong!")
    await bot.process_commands(message)
    



bot.run(token,  log_handler=handler, log_level=logging.DEBUG)






