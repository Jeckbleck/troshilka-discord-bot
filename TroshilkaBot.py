import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import git
from pydub import AudioSegment
import json

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

UPLOADS_DIR = "audio_files/"
SOUNDBOARD_FILE = "soundboard.json"
REPO_PATH = "/home/user/troshilka-discord-bot"

os.makedirs(UPLOADS_DIR, exist_ok=True)

def load_soundboard():
    if os.path.exists(SOUNDBOARD_FILE):
        with open(SOUNDBOARD_FILE, "r") as f:
            return json.load(f)
    return {}

def save_soundboard():
    with open(SOUNDBOARD_FILE, "w") as f:
        json.dump(soundboard, f, indent=4)

soundboard = load_soundboard()

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
async def on_message(message):
    """Handles file uploads and adds them to the soundboard only if '!upload' is used with an attachment."""
    if message.author == bot.user:
        return

    if message.content.startswith("!upload") and message.attachments:
        attachment = message.attachments[0]
        if attachment.filename.endswith((".mp3", ".wav", ".ogg")):
            file_path = f"{UPLOADS_DIR}{attachment.filename}"
            await attachment.save(file_path)

            sound_key = os.path.splitext(attachment.filename)[0]
            soundboard[sound_key] = file_path
            save_soundboard()

            await commit_to_repo(file_path, attachment.filename)
            await message.channel.send(f"File '{attachment.filename}' saved, added to the soundboard, and committed to the repository!")
        else:
            await message.channel.send("Please upload a valid audio file (mp3, wav, ogg) with the '!upload' command.")
    elif message.content.startswith("!upload"):
        await message.channel.send("Please attach an audio file to upload.")

    await bot.process_commands(message)

async def commit_to_repo(file_path, filename):
    """Automatically commits the uploaded audio file to the repository."""
    repo = git.Repo(REPO_PATH)
    dst_path = os.path.join(REPO_PATH, "audio_files", filename)
    os.replace(file_path, dst_path) 

    repo.index.add([dst_path])
    repo.index.commit(f"Added {filename} via bot")
    origin = repo.remote(name="origin")
    origin.push()


@bot.tree.command(name="process", description="Trim the uploaded audio file")
async def process_audio(interaction: discord.Interaction, filename: str, start: int, end: int):
    """Processes an uploaded audio file by trimming to user-specified start and end times."""
    filepath = f"{UPLOADS_DIR}{filename}"
    if os.path.exists(filepath):
        try:
            audio = AudioSegment.from_file(filepath)
            trimmed_audio = audio[start * 1000:end * 1000]

            processed_path = f"{UPLOADS_DIR}processed_{filename}"
            trimmed_audio.export(processed_path, format="mp3")

            sound_key = os.path.splitext(filename)[0]
            soundboard[sound_key] = processed_path
            save_soundboard()

            await interaction.response.send_message(f"Audio trimmed and updated in the soundboard! Use /commit to push it to the repository.")
        except Exception as e:
            await interaction.response.send_message(f"Error processing audio: {e}")
    else:
        await interaction.response.send_message("File not found. Make sure you've uploaded it.")

@bot.tree.command(name="commit", description="Commit and push the processed audio to the repository")
async def commit_audio(interaction: discord.Interaction, filename: str):
    """Adds the processed audio to the repo and pushes to Git."""
    processed_path = f"{UPLOADS_DIR}processed_{filename}"
    if os.path.exists(processed_path):
        repo = git.Repo(REPO_PATH)
        dst_path = os.path.join(REPO_PATH, "audio_files", filename)
        os.replace(processed_path, dst_path)  

        repo.index.add([dst_path])
        repo.index.commit(f"Added {filename} via bot")
        origin = repo.remote(name="origin")
        origin.push()
        await interaction.response.send_message(f"File '{filename}' committed and pushed to the repository.")
    else:
        await interaction.response.send_message("Processed file not found. Make sure you've processed it first.")

@bot.event
async def on_ready():
    """Synchronize commands and display a login message."""
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
