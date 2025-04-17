import logging
import os
import re
import tempfile
from datetime import datetime

import yt_dlp
from django.core.management.base import BaseCommand
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)

from bot.models import Download, User

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit


def get_or_create_user(update: Update) -> User:
    """Create or update user in database using BigIntegerField"""
    user_data = update.effective_user
    return User.objects.get_or_create(
        telegram_id=user_data.id,  # Directly use integer ID
        defaults={
            "username": user_data.username,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name or "",
            "language_code": user_data.language_code or "",
        },
    )[0]  # Return the User instance


def start(update: Update, context: CallbackContext):
    """Improved start command with single user creation call"""
    user = get_or_create_user(update)

    welcome_msg = (
        f"Welcome {user.first_name} to YouTube Downloader Bot!\n\n"
        "Send me a YouTube link to download videos or extract audio.\n"
        "Use /help to see all available commands."
    )

    reply_markup = ReplyKeyboardMarkup(
        [["/help", "/stats"]], resize_keyboard=True, persistent=True
    )
    update.message.reply_text(welcome_msg, reply_markup=reply_markup)


def help_command(update: Update, context: CallbackContext):
    """Show help information"""
    help_text = (
        "🤖 *YouTube Downloader Bot Help*\n\n"
        "Simply send a YouTube link, and I'll give you options to download as video or audio.\n\n"
        "*Commands:*\n"
        "/start - Start the bot\n"
        "/stats - View your download statistics\n"
        "/help - Show this help message\n\n"
        "*Supported formats:*\n"
        "- YouTube videos\n"
        "- YouTube shorts\n\n"
        "The bot will automatically detect YouTube links in your messages."
    )

    update.message.reply_text(help_text, parse_mode="Markdown")


def stats_command(update: Update, context: CallbackContext):
    """Show user's download statistics"""
    user = get_or_create_user(update)

    # Get statistics from database
    total_downloads = Download.objects.filter(user=user).count()
    successful_downloads = Download.objects.filter(user=user, success=True).count()
    video_downloads = Download.objects.filter(
        user=user, download_type="VIDEO", success=True
    ).count()
    audio_downloads = Download.objects.filter(
        user=user, download_type="AUDIO", success=True
    ).count()

    # Calculate success rate
    success_rate = 0
    if total_downloads > 0:
        success_rate = (successful_downloads / total_downloads) * 100

    # Calculate days active
    days_active = (datetime.now().date() - user.created_at.date()).days + 1

    stats_message = (
        f"📊 *Your Download Statistics*\n\n"
        f"👤 User: {user.username or user.first_name}\n"
        f"📆 Member since: {user.created_at.strftime('%Y-%m-%d')}\n"
        f"⏱ Days active: {days_active}\n\n"
        f"📥 Total downloads: {total_downloads}\n"
        f"✅ Successful downloads: {successful_downloads}\n"
        f"📈 Success rate: {success_rate:.1f}%\n"
        f"🎬 Video downloads: {video_downloads}\n"
        f"🎵 Audio downloads: {audio_downloads}\n"
    )

    update.message.reply_text(stats_message, parse_mode="Markdown")


def handle_youtube_url(update: Update, context: CallbackContext):
    """Handle YouTube URLs"""
    url = update.message.text.strip()

    # Create inline keyboard with download options
    keyboard = [
        [
            InlineKeyboardButton("Video 📹", callback_data=f"dl_video_{url}"),
            InlineKeyboardButton("Audio 🎵", callback_data=f"dl_audio_{url}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Please select the download format:", reply_markup=reply_markup
    )


def handle_callback(update: Update, context: CallbackContext):
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    query.answer()  # Answer the callback query

    if query.data.startswith(("dl_video_", "dl_audio_")):
        parts = query.data.split("_", 2)
        download_type = parts[1].upper()  # VIDEO or AUDIO
        url = parts[2]

        # Send processing message
        processing_msg = query.edit_message_text(
            "⏳ Processing your request. This may take a few moments..."
        )

        # Process the download
        download_video(
            update=update,
            context=context,
            url=url,
            download_type=download_type,
            processing_msg=processing_msg,
        )


def download_video(
    update: Update, context: CallbackContext, url, download_type, processing_msg
):
    """Download a video/audio from YouTube and send it to the user"""
    user = get_or_create_user(update)

    # Get video info
    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_title = info_dict.get("title", "Unknown Title")
            duration = info_dict.get("duration", 0)
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        context.bot.edit_message_text(
            text=f"❌ Error getting video information: {str(e)}",
            chat_id=processing_msg.chat_id,
            message_id=processing_msg.message_id,
        )
        return

    # Create download record in database
    download = Download.objects.create(
        user=user,
        youtube_url=url,
        video_title=video_title,
        download_type=download_type,
        success=False,
    )

    # Check if the video is too long (10 minutes max)
    if duration > 600:  # 10 minutes
        context.bot.edit_message_text(
            text="❌ Video is too long. Maximum duration is 10 minutes.",
            chat_id=processing_msg.chat_id,
            message_id=processing_msg.message_id,
        )
        download.error_message = "Video too long"
        download.save()
        return

    # Set up download options
    download_options = {
        "format": "best" if download_type == "VIDEO" else "bestaudio/best",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    if download_type == "AUDIO":
        download_options.update(
            {
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )

    # Perform the download
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            # Change to temporary directory
            original_dir = os.getcwd()
            os.chdir(tmp_dir)

            # Download the file
            with yt_dlp.YoutubeDL(download_options) as ydl:
                ydl.download([url])

            # Find the downloaded file
            files = os.listdir()
            if not files:
                raise Exception("No files were downloaded")

            file_path = os.path.join(tmp_dir, files[0])
            file_size = os.path.getsize(file_path)

            # Check if file is too large for Telegram
            if file_size > MAX_FILE_SIZE:
                raise Exception(
                    f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds Telegram's limit (50MB)"
                )

            # Update processing message
            context.bot.edit_message_text(
                text=f"✅ Sending your {'video' if download_type == 'VIDEO' else 'audio'}...",
                chat_id=processing_msg.chat_id,
                message_id=processing_msg.message_id,
            )

            # Send the file
            with open(file_path, "rb") as file:
                if download_type == "VIDEO":
                    context.bot.send_video(
                        chat_id=processing_msg.chat_id,
                        video=file,
                        caption=f"🎬 {video_title}",
                        timeout=120,
                    )
                else:
                    context.bot.send_audio(
                        chat_id=processing_msg.chat_id,
                        audio=file,
                        title=video_title,
                        timeout=120,
                    )

            # Update success message
            context.bot.edit_message_text(
                text=f"✅ Download complete!\n🎬 {video_title}",
                chat_id=processing_msg.chat_id,
                message_id=processing_msg.message_id,
            )

            # Update download record
            download.success = True
            download.file_size = file_size
            download.completed_at = datetime.now()
            download.save()

        except Exception as e:
            error_message = str(e)
            logger.error(f"Download error: {error_message}")

            # Send error message to user
            context.bot.edit_message_text(
                text=f"❌ Download failed: {error_message}",
                chat_id=processing_msg.chat_id,
                message_id=processing_msg.message_id,
            )

            # Update download record
            download.error_message = error_message
            download.save()

        finally:
            # Change back to original directory
            os.chdir(original_dir)


def handle_message(update: Update, context: CallbackContext):
    """Handle messages that are not commands"""
    message_text = update.message.text

    # Check if the message contains a YouTube URL
    youtube_pattern = (
        r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+"
    )
    if re.search(youtube_pattern, message_text):
        handle_youtube_url(update, context)
    else:
        update.message.reply_text(
            "Please send a valid YouTube link. Use /help for more information."
        )


class Command(BaseCommand):
    help = "Run YouTube Downloader Telegram Bot"

    def handle(self, *args, **kwargs):
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            self.stdout.write(
                self.style.ERROR("TELEGRAM_TOKEN not found in environment")
            )
            return

        updater = Updater(token=token, use_context=True)
        updater.bot.delete_webhook()

        dp = updater.dispatcher

        # Add handlers
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_command))
        dp.add_handler(CommandHandler("stats", stats_command))
        dp.add_handler(CallbackQueryHandler(handle_callback))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

        self.stdout.write(self.style.SUCCESS("YouTube Bot is running..."))
        updater.start_polling()
        updater.idle()
