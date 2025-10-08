import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

# Google AI Studio Configuration
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY')
if not GOOGLE_AI_API_KEY:
    raise ValueError("GOOGLE_AI_API_KEY не найден в переменных окружения")

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bonus_education.db')

# Bot Configuration
BOT_NAME = os.getenv('BOT_NAME', 'Bonus Education - Турецкий язык')
BOT_DESCRIPTION = os.getenv('BOT_DESCRIPTION', 'AI-помощник учебного центра Bonus Education по изучению турецкого языка')

# AI Configuration
AI_MODEL = "gemini-pro"
MAX_TOKENS = 1000
TEMPERATURE = 0.7
