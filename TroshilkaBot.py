import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

soundboard = {
    "stoyan_kolev": "audio_files/stoyan2.mp3",
}

queue = {}

async def play_next_in_queue(interaction):
    """Plays the next audio in the queue, if available."""
    guild_id = interaction.guild.id
    if queue[guild_id]:
        next_sound = queue[guild_id].pop(0)
        source = discord.FFmpegPCMAudio(next_sound)
        interaction.guild.voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next_in_queue(interaction), bot.loop
            )
        )

@bot.tree.command(name="play", description="Play a sound from the soundboard")
async def play_sound(interaction: discord.Interaction, sound_name: str):
    """Adds a sound to the queue and plays it if no other audio is playing."""
    if not interaction.user.voice:
        await interaction.response.send_message("You need to be in a voice channel to use this command.")
        return

    guild_id = interaction.guild.id

    if guild_id not in queue:
        queue[guild_id] = []

    if sound_name in soundboard:
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()

        queue[guild_id].append(soundboard[sound_name])
        if not interaction.guild.voice_client.is_playing():
            await play_next_in_queue(interaction)
        await interaction.response.send_message(f"Added '{sound_name}' to the queue.")
    else:
        available_sounds = ', '.join(soundboard.keys())
        await interaction.response.send_message(f"Error: The sound '{sound_name}' does not exist. Please choose from: {available_sounds}")

@bot.tree.command(name="stop", description="Stop the current audio and clear the queue")
async def stop(interaction: discord.Interaction):
    """Stops current playback and clears the queue."""
    if interaction.guild.voice_client:
        queue[interaction.guild.id].clear()
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Audio playback stopped, and the queue is cleared.")

@bot.tree.command(name="next", description="Skip the current audio and play the next one in the queue")
async def next_audio(interaction: discord.Interaction):
    """Skips the current audio and plays the next one in the queue, if available."""
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped to the next audio in the queue.")
    else:
        await interaction.response.send_message("There's no audio currently playing to skip.")

@bot.tree.command(name="list_sounds", description="List all available sounds")
async def list_sounds(interaction: discord.Interaction):
    """Lists all sounds in the soundboard."""
    sound_list = "\n".join([f"- {name}" for name in soundboard.keys()])
    await interaction.response.send_message(f"**Available Sounds:**\n{sound_list}")

@bot.tree.command(name="queue", description="Display the current audio queue")
async def show_queue(interaction: discord.Interaction):
    """Displays the current audio queue for the guild."""
    guild_id = interaction.guild.id
    if guild_id in queue and queue[guild_id]:
        queue_list = "\n".join(
            [f"{index + 1}. {os.path.basename(sound_path)}" for index, sound_path in enumerate(queue[guild_id])]
        )
        await interaction.response.send_message(f"**Current Queue:**\n{queue_list}")
    else:
        await interaction.response.send_message("The queue is currently empty.")

@bot.event
async def on_ready():
    """Synchronize commands and display a login message."""
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
