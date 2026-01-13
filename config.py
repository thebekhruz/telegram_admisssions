import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://telegramadmisssions-test.up.railway.app/kommo-webhook')
PORT = int(os.getenv('PORT', 8000))
ADMISSIONS_CHAT_ID = os.getenv('ADMISSIONS_CHAT_ID')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@oxbridge_news')
CHANNEL_LINK = os.getenv('CHANNEL_LINK', 'https://t.me/oxbridge_news')

# Admin IDs (comma separated)
ADMIN_IDS = [int(id_str.strip()) for id_str in os.getenv('ADMIN_IDS', '').split(',') if id_str.strip()]


# Database
DATABASE_URL = os.getenv('DATABASE_URL')

# Campus Info
CAMPUSES = {
    'mu': {
        'name': {
            'ru': 'MU Campus - Мирзо Улугбек',
            'uz': 'MU Campus - Mirzo Ulugbek',
            'en': 'MU Campus - Mirzo Ulugbek',
            'tr': 'MU Campus - Mirzo Ulugbek'
        },
        'address': os.getenv('CAMPUS_MU_ADDRESS', 'Mirzo Ulugbek District, Tashkent'),
        'map': os.getenv('CAMPUS_MU_MAP', 'https://maps.google.com')
    },
    'yashnobod': {
        'name': {
            'ru': 'Yashnobod - Яшнабад',
            'uz': 'Yashnobod',
            'en': 'Yashnobod Campus',
            'tr': 'Yashnobod Kampüsü'
        },
        'address': os.getenv('CAMPUS_YASHNOBOD_ADDRESS', 'Yashnobod District, Tashkent'),
        'map': os.getenv('CAMPUS_YASHNOBOD_MAP', 'https://maps.google.com')
    }
}

# Tour Times
TOUR_TIMES = ['10:00', '14:00', '16:00']

# Contact
CONTACT_PHONE = os.getenv('CONTACT_PHONE', '+998 XX XXX XX XX')
