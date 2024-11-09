import discord
from discord.ext import commands
from discord import app_commands
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
REPO_PATH = "D:/repota/troshilka-discord-bot"

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
    else:
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()

async def sound_name_autocomplete(interaction: discord.Interaction, current: str):
    """Provide autocomplete suggestions for sound names."""
    return [
        app_commands.Choice(name=sound, value=sound)
        for sound in soundboard.keys()
        if current.lower() in sound.lower()
    ][:25]

@bot.tree.command(name="play", description="Play a sound from the soundboard")
@app_commands.autocomplete(sound_name=sound_name_autocomplete)
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
    """Handles multiple file uploads and adds them to the soundboard only if '!upload' is used with attachments."""
    if message.author == bot.user:
        return

    if message.content.startswith("!upload") and message.attachments:
        responses = []
        
        for attachment in message.attachments:
            if attachment.filename.endswith((".mp3", ".wav", ".ogg")):
                temp_path = f"{UPLOADS_DIR}{attachment.filename}"
                await attachment.save(temp_path)

                audio = AudioSegment.from_file(temp_path)
                duration_seconds = len(audio) / 1000  

                if duration_seconds > 20:
                    os.remove(temp_path)
                    responses.append(f"The audio file `{attachment.filename}` is too long (over 20 seconds). Please upload a shorter file.")
                    continue

                base_name = os.path.splitext(attachment.filename)[0].lower()
                if base_name in soundboard:
                    os.remove(temp_path) 
                    responses.append(f"The sound effect `{base_name}` is already present in the soundboard.")
                    continue

                file_path = temp_path
                soundboard[base_name] = file_path
                save_soundboard()
                responses.append(f"File `{attachment.filename}` saved and added to the soundboard as `{base_name}`.")
            else:
                responses.append(f"`{attachment.filename}` is not a valid audio file (mp3, wav, ogg).")

        await message.channel.send("\n".join(responses))
    elif message.content.startswith("!upload"):
        await message.channel.send("Please attach one or more audio files to upload.")

    await bot.process_commands(message)

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

@bot.tree.command(name="commit", description="Commit and push all new audios to the repository")
async def commit_audio(interaction: discord.Interaction):
    """Commits all audio files in the audio_files directory to the repository with a general message."""
    repo = git.Repo(REPO_PATH)
    audio_files_dir = os.path.join(REPO_PATH, "audio_files")
    
    repo.index.add([os.path.join("audio_files", file) for file in os.listdir(audio_files_dir)])
    
    repo.index.commit("Added new audios to the library")
    origin = repo.remote(name="origin")
    origin.push()

    await interaction.response.send_message("All new audios have been committed and pushed to the repository.")

@bot.tree.command(name="help", description="List all available commands and their descriptions")
async def help_command(interaction: discord.Interaction):
    """Sends a help message listing all commands and their descriptions."""
    help_text = """
**Available Commands:**

`/play <sound_name>` - Play a sound from the soundboard. Requires you to be in a voice channel. Autocompletes available sound names.

`/stop` - Stop the current audio and clear the queue.

`/next` - Skip the current audio and play the next one in the queue.

`!upload` - Handles multiple file uploads and adds them to the soundboard only if '!upload' is used with attachments.

`/list_sounds` - List all available sounds in the soundboard.

`/queue` - Display the current audio queue for the guild.

⛔`/process <filename> <start> <end>` - Trim the uploaded audio file between the specified start and end times (in seconds) and add the trimmed version to the soundboard.

⛔`/commit` - Commit and push all new audio files to the repository with a general commit message.

`/help` - Display this help message with a list of available commands.
    """
    await interaction.response.send_message(help_text)

@bot.event
async def on_ready():
    """Synchronize commands and display a login message."""
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))