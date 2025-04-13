# youtube_telegram_bot.py
# Telegram bot with Django analytics integration

import os
import telebot
import yt_dlp
import requests
import json
import tempfile
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DJANGO_API_URL = os.environ.get('DJANGO_API_URL', 'http://localhost:8000/api/')
API_KEY = os.environ.get('BOT_API_KEY', 'your-api-key-here')  # Should match settings.BOT_API_KEY in Django

# Initialize the bot
bot = telebot.TeleBot(BOT_TOKEN)

# Helper function for API requests
def api_request(endpoint, data=None, method='post'):
    """Make a request to the Django API with proper headers and error handling."""
    url = f"{DJANGO_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY
    }
    
    try:
        if method.lower() == 'get':
            response = requests.get(url, headers=headers)
        else:
            response = requests.post(url, data=json.dumps(data), headers=headers)
        
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response.json()
    
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return {'status': 'error', 'message': f"Communication with analytics server failed: {str(e)}"}

# Register a user when they start the bot
@bot.message_handler(commands=['start'])
def start(message):
    user_data = {
        'telegram_id': str(message.from_user.id),
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name,
        'language_code': message.from_user.language_code
    }
    
    # Register the user in the analytics system
    response = api_request('register-user/', user_data)
    
    if response.get('status') == 'success':
        bot.reply_to(message, 
                    f"Welcome to YouTube Downloader Bot! Send me a YouTube link to download it as video or audio.\n"
                    f"Use /help to see all commands.")
    else:
        bot.reply_to(message, "Welcome! Send me a YouTube link to download it as video or audio.")
        logger.error(f"Failed to register user: {response.get('message')}")

# Handle YouTube URLs
@bot.message_handler(regexp=r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+')
def handle_youtube_url(message):
    url = message.text.strip()
    
    # Show options for download format
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("Video", callback_data=f"dl_video_{url}"),
        telebot.types.InlineKeyboardButton("Audio", callback_data=f"dl_audio_{url}")
    )
    
    bot.reply_to(message, "Please select the download format:", reply_markup=markup)

# Process download format selection
@bot.callback_query_handler(func=lambda call: call.data.startswith(('dl_video_', 'dl_audio_')))
def download_callback(call):
    try:
        # Parse callback data
        parts = call.data.split('_', 2)
        download_type = parts[1].upper()  # VIDEO or AUDIO
        url = parts[2]
        
        # Show "processing" message
        bot.answer_callback_query(call.id, "Starting download...")
        processing_msg = bot.edit_message_text(
            "⏳ Processing your request. This may take a few moments...",
            call.message.chat.id,
            call.message.message_id
        )
        
        # Get video info first
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_title = info_dict.get('title', 'Unknown Title')
        
        # Start analytics tracking
        user_id = call.from_user.id
        start_data = {
            'telegram_id': str(user_id),
            'youtube_url': url,
            'video_title': video_title,
            'download_type': download_type
        }
        
        # Record the start of download
        start_response = api_request('start-download/', start_data)
        activity_id = start_response.get('activity_id')
        
        # Set up download options
        download_options = {
            'format': 'best' if download_type == 'VIDEO' else 'bestaudio/best',
            'outtmpl': '%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True
        }
        
        if download_type == 'AUDIO':
            download_options.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        
        # Perform the download
        start_time = datetime.now()
        download_success = False
        error_message = None
        file_path = None
        file_size = 0
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                # Change working directory to temp directory
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
                download_success = True
                
                # Send the file to the user
                bot.edit_message_text(
                    f"✅ Sending your {'video' if download_type == 'VIDEO' else 'audio'}...",
                    call.message.chat.id,
                    processing_msg.message_id
                )
                
                with open(file_path, 'rb') as file:
                    if download_type == 'VIDEO':
                        bot.send_video(
                            call.message.chat.id,
                            file,
                            caption=f"🎬 {video_title}",
                            timeout=120
                        )
                    else:
                        bot.send_audio(
                            call.message.chat.id,
                            file,
                            title=video_title,
                            timeout=120
                        )
                
                # Send confirmation message
                bot.edit_message_text(
                    f"✅ Download complete!\n🎬 {video_title}",
                    call.message.chat.id,
                    processing_msg.message_id
                )
                
            except Exception as e:
                error_message = str(e)
                logger.error(f"Download error: {error_message}")
                download_success = False
                
                # Send error message to user
                bot.edit_message_text(
                    f"❌ Download failed: {error_message}",
                    call.message.chat.id,
                    processing_msg.message_id
                )
            
            finally:
                # Change back to original directory
                os.chdir(original_dir)
        
        # Record download completion in analytics
        if activity_id:
            complete_data = {
                'activity_id': activity_id,
                'success': download_success,
                'file_size': file_size,
                'error_message': error_message
            }
            api_request('complete-download/', complete_data)
        
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        try:
            bot.edit_message_text(
                f"❌ An error occurred: {str(e)}",
                call.message.chat.id,
                call.message.message_id
            )
        except:
            pass

# Handle /stats command
@bot.message_handler(commands=['stats'])
def show_stats(message):
    user_id = message.from_user.id
    
    # Get user stats from API
    response = api_request(f'user-stats/{user_id}/', method='get')
    
    if response.get('status') == 'success':
        stats = response.get('stats', {})
        user_info = response.get('user', {})
        
        stats_message = (
            f"📊 *Your Download Statistics*\n\n"
            f"👤 User: {user_info.get('username') or user_info.get('first_name', 'User')}\n"
            f"📆 Member since: {user_info.get('join_date')}\n"
            f"⏱ Days active: {user_info.get('days_active')}\n\n"
            f"📥 Total downloads: {stats.get('total_downloads', 0)}\n"
            f"✅ Successful downloads: {stats.get('successful_downloads', 0)}\n"
            f"📈 Success rate: {stats.get('success_rate', 0):.1f}%\n"
            f"🎬 Video downloads: {stats.get('video_downloads', 0)}\n"
            f"🎵 Audio downloads: {stats.get('audio_downloads', 0)}\n"
        )
        
        bot.reply_to(message, stats_message, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Failed to retrieve your statistics. Please try again later.")

# Handle /help command
@bot.message_handler(commands=['help'])
def show_help(message):
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
    
    bot.reply_to(message, help_text, parse_mode="Markdown")

# Handle all other messages
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Please send a valid YouTube link. Use /help for more information.")

# Start the bot
if __name__ == '__main__':
    logger.info("Bot started")
    bot.polling(none_stop=True)