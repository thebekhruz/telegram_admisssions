import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN')
ADMISSIONS_CHAT_ID = os.getenv('ADMISSIONS_CHAT_ID')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@oxbridge_news')
CHANNEL_LINK = os.getenv('CHANNEL_LINK', 'https://t.me/oxbridge_news')

# amoCRM
AMOCRM_SUBDOMAIN = os.getenv('AMOCRM_SUBDOMAIN')
AMOCRM_DOMAIN = os.getenv('AMOCRM_DOMAIN', 'amocrm.ru')  # or amocrm.com
AMOCRM_CLIENT_ID = os.getenv('AMOCRM_CLIENT_ID')
AMOCRM_CLIENT_SECRET = os.getenv('AMOCRM_CLIENT_SECRET')
AMOCRM_ACCESS_TOKEN = os.getenv('AMOCRM_ACCESS_TOKEN')
AMOCRM_REFRESH_TOKEN = os.getenv('AMOCRM_REFRESH_TOKEN')
AMOCRM_PIPELINE_ID = int(os.getenv('AMOCRM_PIPELINE_ID', 0))
AMOCRM_STATUS_ID = int(os.getenv('AMOCRM_STATUS_ID', 0))
AMOCRM_API_URL = f"https://{AMOCRM_SUBDOMAIN}.{AMOCRM_DOMAIN}/api/v4"

PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL')
PORT = int(os.getenv('PORT', '8000'))

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
