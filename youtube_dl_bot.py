import json
import logging
import os
import re
from pathlib import Path

import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your Telegram Bot Token from BotFather
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# YouTube URL regex pattern
YOUTUBE_REGEX = r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"

# Store user download preferences
user_preferences = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Welcome to YouTube Downloader Bot!\n\n"
        "Just send me a YouTube link, and I'll help you download it as video or audio.\n"
        "Use /help to learn more about what I can do."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "🎬 *YouTube Downloader Bot Help*\n\n"
        "Simply send me a YouTube link and choose your preferred format:\n"
        "• 🎥 *Video* - Download as MP4 video\n"
        "• 🎵 *Audio* - Extract audio as MP3\n\n"
        "*Video Quality Options:*\n"
        "• High (720p)\n"
        "• Medium (480p)\n"
        "• Low (360p)\n\n"
        "*Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/settings - Change your default preferences\n"
        "/about - About this bot\n\n"
        "*Note:* Files are limited to 50MB due to Telegram restrictions.",
        parse_mode="Markdown",
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send information about the bot."""
    await update.message.reply_text(
        "🤖 *YouTube Downloader Bot*\n\n"
        "This bot uses yt-dlp to download videos from YouTube.\n"
        "Created for personal use only.\n"
        "Please respect YouTube's Terms of Service.\n\n"
        "📦 Containerized with Docker for easy deployment.",
        parse_mode="Markdown",
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow users to set their default preferences."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🎥 Video as default", callback_data="set_default_video"
            ),
            InlineKeyboardButton(
                "🎵 Audio as default", callback_data="set_default_audio"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Reset preferences", callback_data="reset_preferences"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    user_id = update.effective_user.id
    current_preference = user_preferences.get(user_id, {}).get(
        "default_format", "None set"
    )

    await update.message.reply_text(
        f"⚙️ *User Settings*\n\n"
        f"Current default format: *{current_preference}*\n\n"
        "Choose your default download format:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def handle_settings_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Process settings callback queries."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in user_preferences:
        user_preferences[user_id] = {}

    if query.data == "set_default_video":
        user_preferences[user_id]["default_format"] = "Video"
        await query.edit_message_text(
            "✅ Your default preference has been set to *Video*.\n"
            "You can still select different options for each download.",
            parse_mode="Markdown",
        )
    elif query.data == "set_default_audio":
        user_preferences[user_id]["default_format"] = "Audio"
        await query.edit_message_text(
            "✅ Your default preference has been set to *Audio*.\n"
            "You can still select different options for each download.",
            parse_mode="Markdown",
        )
    elif query.data == "reset_preferences":
        if user_id in user_preferences:
            del user_preferences[user_id]
        await query.edit_message_text(
            "✅ Your preferences have been reset.\n"
            "You'll be asked to choose format options for each download.",
            parse_mode="Markdown",
        )


async def process_youtube_link(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Process YouTube link and offer download options."""
    message_text = update.message.text
    youtube_match = re.search(YOUTUBE_REGEX, message_text)

    if not youtube_match:
        await update.message.reply_text("Please send a valid YouTube URL.")
        return

    youtube_url = youtube_match.group(0)

    try:
        # Fetch video information
        status_message = await update.message.reply_text(
            "🔍 Fetching video information..."
        )

        # Setup yt-dlp options for info extraction only
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        # Extract video information
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            video_title = info.get("title", "Unknown Title")
            duration = info.get("duration", 0)
            thumbnail = info.get("thumbnail", "")

        # Check if the video is too long (>20 minutes)
        if duration > 1200:  # 20 minutes in seconds
            await status_message.edit_text(
                f"⚠️ This video is {duration // 60} minutes long, which may exceed Telegram's file size limits.\n"
                "Only the first part might be downloadable."
            )

        # Store context for callbacks
        context.user_data["current_download"] = {
            "url": youtube_url,
            "title": video_title,
            "status_message_id": status_message.message_id,
        }

        # Create download options keyboard
        user_id = update.effective_user.id
        default_format = user_preferences.get(user_id, {}).get("default_format")

        if default_format:
            # Use user's default preference
            if default_format == "Video":
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🎥 High Quality (720p)", callback_data="dl_video_high"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎥 Medium Quality (480p)", callback_data="dl_video_medium"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎥 Low Quality (360p)", callback_data="dl_video_low"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎵 Download as Audio", callback_data="dl_audio"
                        )
                    ],
                    [InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")],
                ]
            else:  # Audio default
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🎵 Download as Audio", callback_data="dl_audio"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎥 High Quality (720p)", callback_data="dl_video_high"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎥 Medium Quality (480p)", callback_data="dl_video_medium"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🎥 Low Quality (360p)", callback_data="dl_video_low"
                        )
                    ],
                    [InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")],
                ]
        else:
            # No preference set, show standard options
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🎥 Video", callback_data="show_video_options"
                    ),
                    InlineKeyboardButton("🎵 Audio", callback_data="dl_audio"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")],
            ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send video information and download options
        await status_message.edit_text(
            f"📺 *{video_title}*\n\n"
            f"Duration: {format_duration(duration)}\n\n"
            "Please select your download format:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error processing YouTube link: {e}")
        await update.message.reply_text(f"❌ Error processing video: {str(e)}")


def format_duration(seconds):
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries for download options."""
    query = update.callback_query
    await query.answer()

    # Skip if this is a settings callback
    if query.data.startswith("set_default") or query.data == "reset_preferences":
        return

    # Get download info from context
    download_info = context.user_data.get("current_download", {})
    if not download_info:
        await query.edit_message_text(
            "❌ Download session expired. Please send the YouTube link again."
        )
        return

    youtube_url = download_info.get("url")
    video_title = download_info.get("title")

    if query.data == "dl_cancel":
        await query.edit_message_text("✅ Download cancelled.")
        return

    if query.data == "show_video_options":
        # Show video quality options
        keyboard = [
            [
                InlineKeyboardButton(
                    "🎥 High Quality (720p)", callback_data="dl_video_high"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎥 Medium Quality (480p)", callback_data="dl_video_medium"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎥 Low Quality (360p)", callback_data="dl_video_low"
                )
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="show_main_options")],
            [InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📺 *{video_title}*\n\nChoose video quality:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
        return

    if query.data == "show_main_options":
        # Go back to main options
        keyboard = [
            [
                InlineKeyboardButton("🎥 Video", callback_data="show_video_options"),
                InlineKeyboardButton("🎵 Audio", callback_data="dl_audio"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📺 *{video_title}*\n\nPlease select your download format:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
        return

    # Process download requests
    await query.edit_message_text(
        f"⏳ Processing your request...\nPreparing to download {video_title}"
    )

    chat_id = update.effective_chat.id
    download_dir = f"downloads/{chat_id}"
    os.makedirs(download_dir, exist_ok=True)

    try:
        if query.data == "dl_audio":
            await download_audio(
                update, context, youtube_url, video_title, download_dir
            )
        elif query.data.startswith("dl_video"):
            quality = query.data.split("_")[-1]
            await download_video(
                update, context, youtube_url, video_title, download_dir, quality
            )
    except Exception as e:
        logger.error(f"Download error: {e}")
        await query.edit_message_text(f"❌ Download failed: {str(e)}")


async def download_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    youtube_url: str,
    video_title: str,
    download_dir: str,
    quality: str,
) -> None:
    """Download YouTube video with specified quality."""
    query = update.callback_query

    # Set format based on quality
    if quality == "high":
        format_spec = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]"
        quality_text = "High Quality (720p)"
    elif quality == "medium":
        format_spec = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]"
        quality_text = "Medium Quality (480p)"
    else:  # low
        format_spec = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]"
        quality_text = "Low Quality (360p)"

    await query.edit_message_text(
        f"📥 Downloading: {video_title}\n👉 Format: 🎥 {quality_text}\n⏳ Please wait..."
    )

    # Setup yt-dlp options
    ydl_opts = {
        "format": format_spec,
        "outtmpl": f"{download_dir}/%(title)s-%(id)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": False,
        "no_warnings": False,
        "default_search": "auto",
        "merge_output_format": "mp4",
    }

    # Download the video
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        video_filename = ydl.prepare_filename(info)

        # Ensure we have an mp4 file (in case the merger didn't produce one)
        if not video_filename.endswith(".mp4"):
            base_filename = os.path.splitext(video_filename)[0]
            potential_mp4 = f"{base_filename}.mp4"
            if os.path.exists(potential_mp4):
                video_filename = potential_mp4

    await query.edit_message_text(f"✅ Download complete!\n⏳ Uploading to Telegram...")

    # Check file size
    file_size = os.path.getsize(video_filename)
    if file_size > 50 * 1024 * 1024:  # 50MB
        await query.edit_message_text(
            "⚠️ The video is larger than 50MB and can't be sent via Telegram.\n"
            "Trying with a lower quality..."
        )

        # Try with lower quality if current quality isn't already low
        if quality != "low":
            os.remove(video_filename)
            await download_video(
                update, context, youtube_url, video_title, download_dir, "low"
            )
            return
        else:
            # If already using lowest quality, try audio only
            await query.edit_message_text(
                "⚠️ Even the lowest video quality exceeds Telegram's size limit.\n"
                "Would you like to download audio only?"
            )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🎵 Download Audio Instead", callback_data="dl_audio"
                    )
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "⚠️ Video too large for Telegram (50MB limit).\n"
                "Would you like to download audio only?",
                reply_markup=reply_markup,
            )

            os.remove(video_filename)
            return

    # Send the video file
    with open(video_filename, "rb") as video_file:
        message = await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=video_file,
            caption=f"📹 *{video_title}*\n🎞️ Format: {quality_text}",
            parse_mode="Markdown",
            supports_streaming=True,
        )

    # Cleanup
    os.remove(video_filename)
    await query.edit_message_text(
        f"✅ Video downloaded successfully!\n"
        f"📹 *{video_title}*\n"
        f"🎞️ Format: {quality_text}",
        parse_mode="Markdown",
    )


async def download_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    youtube_url: str,
    video_title: str,
    download_dir: str,
) -> None:
    """Extract and download audio from YouTube video."""
    query = update.callback_query

    await query.edit_message_text(
        f"📥 Downloading audio for: {video_title}\n⏳ Please wait..."
    )

    # Setup yt-dlp options for audio extraction
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{download_dir}/%(title)s-%(id)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    # Download the audio
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        # Get the expected filename (before post-processing)
        original_filename = ydl.prepare_filename(info)
        # Replace extension with mp3 since we're extracting audio
        audio_filename = os.path.splitext(original_filename)[0] + ".mp3"

    await query.edit_message_text(
        f"✅ Audio extraction complete!\n⏳ Uploading to Telegram..."
    )

    # Check if file exists and size
    if not os.path.exists(audio_filename):
        all_files = os.listdir(download_dir)
        matching_files = [
            f
            for f in all_files
            if f.startswith(os.path.basename(os.path.splitext(original_filename)[0]))
        ]

        if matching_files:
            audio_filename = os.path.join(download_dir, matching_files[0])
        else:
            await query.edit_message_text("❌ Could not find the extracted audio file.")
            return

    file_size = os.path.getsize(audio_filename)
    if file_size > 50 * 1024 * 1024:  # 50MB
        await query.edit_message_text(
            "⚠️ The audio file is larger than 50MB and can't be sent via Telegram.\n"
            "Trying with a lower quality..."
        )

        os.remove(audio_filename)

        # Try with lower quality
        ydl_opts["postprocessors"][0]["preferredquality"] = "96"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(youtube_url, download=True)

        if (
            not os.path.exists(audio_filename)
            or os.path.getsize(audio_filename) > 50 * 1024 * 1024
        ):
            await query.edit_message_text(
                "❌ Sorry, even the compressed audio exceeds Telegram's file size limit."
            )
            if os.path.exists(audio_filename):
                os.remove(audio_filename)
            return

    # Send the audio file
    with open(audio_filename, "rb") as audio_file:
        await context.bot.send_audio(
            chat_id=update.effective_chat.id,
            audio=audio_file,
            title=video_title,
            caption=f"🎵 *{video_title}*\nExtracted audio from YouTube",
            parse_mode="Markdown",
        )

    # Cleanup
    os.remove(audio_filename)
    await query.edit_message_text(
        f"✅ Audio downloaded successfully!\n🎵 *{video_title}*",
        parse_mode="Markdown",
    )


def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("settings", settings_command))

    # Add callback query handlers
    application.add_handler(
        CallbackQueryHandler(
            handle_settings_callback, pattern=r"^set_default|reset_preferences"
        )
    )
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Add message handler for YouTube links
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, process_youtube_link)
    )

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
