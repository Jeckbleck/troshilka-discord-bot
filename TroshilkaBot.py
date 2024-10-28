import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='>', intents=intents)

load_dotenv()

soundboard = {
    "stoyan_kolev": "audio_files/stoyan2.mp3",
}

queue = {}

async def play_next_in_queue(ctx):
    """Play the next sound in the queue if there is one."""
    guild_id = ctx.guild.id
    if queue[guild_id]:  # Check if there is more audio in the queue
        next_sound = queue[guild_id].pop(0)
        source = discord.FFmpegPCMAudio(next_sound)
        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_in_queue(ctx), bot.loop))


@bot.command(name='play')
async def play_sound(ctx, sound_name: str):
    if ctx.author.voice:
        guild_id = ctx.guild.id

        # Ensure there's a queue for this guild
        if guild_id not in queue:
            queue[guild_id] = []

        if sound_name in soundboard:
            # Connect to the voice channel if not already connected
            if not ctx.voice_client:
                await ctx.author.voice.channel.connect()

            # Add the sound to the queue
            queue[guild_id].append(soundboard[sound_name])
            
            # If nothing is currently playing, start the next sound
            if not ctx.voice_client.is_playing():
                await play_next_in_queue(ctx)
        else:
            await ctx.send(f"Error: The sound '{sound_name}' does not exist. Please choose from: {', '.join(soundboard.keys())}")
    else:
        await ctx.send("You need to be in a voice channel to use this command.")

@bot.command(name='stop')
async def stop(ctx):
    """Stops the currently playing audio and clears the queue."""
    if ctx.voice_client:
        queue[ctx.guild.id].clear()
        ctx.voice_client.stop()
        await ctx.send("Audio playback stopped, and the queue is cleared.")

@bot.command(name='next')
async def next_audio(ctx):
    """Skips the current audio and plays the next one in the queue."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped to the next audio in the queue.")
    else:
        await ctx.send("There's no audio currently playing to skip.")

@bot.command(name='list_sounds')
async def list_sounds(ctx):
    sound_list = "\n".join([f"- {name}" for name in soundboard.keys()])
    await ctx.send(f"**Available Sounds:**\n{sound_list}")

@bot.command(name='queue')
async def show_queue(ctx):
    """Displays the current audio queue."""
    guild_id = ctx.guild.id
    if guild_id in queue and queue[guild_id]:
        queue_list = "\n".join([f"{index + 1}. {os.path.basename(sound_path)}" for index, sound_path in enumerate(queue[guild_id])])
        await ctx.send(f"**Current Queue:**\n{queue_list}")
    else:
        await ctx.send("The queue is currently empty.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
