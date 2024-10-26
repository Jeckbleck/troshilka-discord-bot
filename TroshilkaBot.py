import discord
from discord.ext import commands
import asyncio

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.command(name='sound_1')
async def play_sound(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()

        source = discord.FFmpegPCMAudio("audio path", executable="ffmpeg path")
        voice_client.play(source, after=lambda e: print("Finished playing sound1"))

        while voice_client.is_playing():
            await asyncio.sleep(1)
        await voice_client.disconnect()
    else:
        await ctx.send("You need to be in a voice channel to use this command.")

bot.run("token")
