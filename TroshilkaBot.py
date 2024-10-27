import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

load_dotenv()

soundboard = {
    "stoyan_kolev": "audio_files/stoyan2.mp3",
}

@bot.command(name='play')
async def play_sound(ctx, sound_name: str):
    if ctx.author.voice:

        if sound_name in soundboard:
            channel = ctx.author.voice.channel
            voice_client = await channel.connect()

            source = discord.FFmpegPCMAudio(soundboard[sound_name], executable="C:/ffmpeg/ffmpeg.exe")
            voice_client.play(source, after=lambda e: print(f"Finished playing {sound_name}"))

            while voice_client.is_playing():
                await asyncio.sleep(1)
            await voice_client.disconnect()
        else:
            await ctx.send(f"Error: The sound '{sound_name}' does not exist. Please choose from: {', '.join(soundboard.keys())}")
    else:
        await ctx.send("You need to be in a voice channel to use this command.")

@bot.command(name='list_sounds')
async def list_sounds(ctx):
    sound_list = "\n".join([f"- {name}" for name in soundboard.keys()])
    await ctx.send(f"**Available Sounds:**\n{sound_list}")

bot.run(os.getenv("DISCORD_TOKEN"))
