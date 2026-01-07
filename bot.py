import logging
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

import config
from database import db
from kommo import KommoAPI
from translations import t, TRANSLATIONS
from scheduler import setup_scheduler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Kommo API
kommo = KommoAPI()


# Utility functions
def get_user_lang(chat_id: int) -> str:
    """Get user's language"""
    return db.get_user_language(chat_id)


def validate_phone(phone: str) -> bool:
    """Validate phone number format (must contain at least 7 digits)"""
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 7


def normalize_phone(phone: str) -> str:
    """Normalize phone number to international format if possible, or return as is"""
    # Get just digits for length check
    digits = re.sub(r'\D', '', phone)
    
    # If exactly 7 digits (User Request) or 9 digits (Standard Local), add +998
    if len(digits) == 7 or len(digits) == 9:
        return f"+998{digits}"

    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # If it starts with 8 and is long enough, assume it's a local number (e.g. RU/UZ)
    # But user asked to keep it simple, so let's just ensure it has a + if it looks international
    if not cleaned.startswith('+') and len(cleaned) > 10:
        return '+' + cleaned
    
    return cleaned


# Feature 1: Language Selection
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Show language selection"""
    chat_id = update.effective_chat.id

    # Create user if not exists
    if not db.get_user(chat_id):
        db.create_user(chat_id)

    keyboard = [
        [
            InlineKeyboardButton(
                TRANSLATIONS['language_selection']['buttons']['ru'],
                callback_data='lang_ru'
            ),
            InlineKeyboardButton(
                TRANSLATIONS['language_selection']['buttons']['uz'],
                callback_data='lang_uz'
            )
        ],
        [
            InlineKeyboardButton(
                TRANSLATIONS['language_selection']['buttons']['en'],
                callback_data='lang_en'
            ),
            InlineKeyboardButton(
                TRANSLATIONS['language_selection']['buttons']['tr'],
                callback_data='lang_tr'
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        TRANSLATIONS['language_selection']['text'],
        reply_markup=reply_markup
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    language = query.data.split('_')[1]  # lang_ru -> ru

    # Update user language
    db.update_user(chat_id, language=language)
    
    # NEW STEP: Ask for Name
    db.set_user_state(chat_id, 'awaiting_name')
    
    # Localized prompts for Name
    prompts = {
        'ru': "Пожалуйста, введите ваше Имя и Фамилию:",
        'en': "Please enter your Name and Surname:",
        'uz': "Iltimos, Ismingiz va Familiyangizni kiriting:",
        'tr': "Lütfen Adınızı ve Soyadınızı giriniz:"
    }
    
    await query.edit_message_text(
        prompts.get(language, prompts['en'])
    )


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle name input"""
    chat_id = update.effective_chat.id
    user = db.get_user(chat_id)
    
    if not user or user['state'] != 'awaiting_name':
        return

    name = update.message.text.strip()
    db.set_user_data(chat_id, 'name', name)
    
    # Move to Phone
    db.set_user_state(chat_id, 'awaiting_phone')
    await update.message.reply_text(t('welcome', user['language']))


# Feature 2: Phone Capture + Kommo Sync
async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number input"""
    chat_id = update.effective_chat.id
    user = db.get_user(chat_id)

    if not user or user['state'] != 'awaiting_phone':
        return

    lang = user['language']
    phone = update.message.text.strip()

    # Validate phone
    if not validate_phone(phone):
        await update.message.reply_text(t('invalid_phone', lang))
        return

    phone = normalize_phone(phone)

    # Save to database
    db.set_user_data(chat_id, 'phone', phone)

    # Sync with Kommo
    contact_id = kommo.create_or_update_contact(
        phone=phone,
        chat_id=chat_id,
        username=update.effective_user.username,
        language=lang,
        name=user.get('name')  # Pass name to save in Contact too
    )

    if contact_id:
        db.set_user_data(chat_id, 'contact_id', contact_id)

    # Move to Feature 3: Basic Qualification
    db.set_user_state(chat_id, 'awaiting_children_count')
    await ask_children_count(update, context)


# Feature 3: Basic Qualification
async def ask_children_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask how many children"""
    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    keyboard = [
        [
            InlineKeyboardButton('1', callback_data='children_1'),
            InlineKeyboardButton('2', callback_data='children_2'),
            InlineKeyboardButton('3', callback_data='children_3'),
            InlineKeyboardButton('4+', callback_data='children_4')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.reply_text(
            t('children_count', lang),
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            t('children_count', lang),
            reply_markup=reply_markup
        )


async def children_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle children count selection"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    count = int(query.data.split('_')[1])
    db.set_user_data(chat_id, 'children_count', count)
    db.set_user_data(chat_id, 'current_child', 1)
    db.set_user_data(chat_id, 'children_ages', [])

    # Ask age for first child
    db.set_user_state(chat_id, 'awaiting_child_age')
    await ask_child_age(query, chat_id, 1, lang)


async def ask_child_age(query, chat_id: int, child_num: int, lang: str):
    """Ask age of child"""
    keyboard = [
        [
            InlineKeyboardButton(
                t('age_groups.3-6', lang),
                callback_data='age_3-6'
            ),
            InlineKeyboardButton(
                t('age_groups.7-10', lang),
                callback_data='age_7-10'
            )
        ],
        [
            InlineKeyboardButton(
                t('age_groups.11-14', lang),
                callback_data='age_11-14'
            ),
            InlineKeyboardButton(
                t('age_groups.15-18', lang),
                callback_data='age_15-18'
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = t('child_age', lang, num=child_num)

    await query.edit_message_text(text, reply_markup=reply_markup)


async def child_age_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle child age selection"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    age_range = query.data.split('_')[1]  # age_3-6 -> 3-6

    # Save age
    ages = db.get_user_data(chat_id, 'children_ages', [])
    ages.append(age_range)
    db.set_user_data(chat_id, 'children_ages', ages)

    # Check if more children
    current_child = db.get_user_data(chat_id, 'current_child', 1)
    children_count = db.get_user_data(chat_id, 'children_count', 1)

    if current_child < children_count:
        # Ask next child
        db.set_user_data(chat_id, 'current_child', current_child + 1)
        await ask_child_age(query, chat_id, current_child + 1, lang)
    else:
        # All children done, ask program interest
        db.set_user_state(chat_id, 'awaiting_program')
        await ask_program_interest(query, chat_id, lang)


async def ask_program_interest(query, chat_id: int, lang: str):
    """Ask which program they're interested in"""
    keyboard = [
        [InlineKeyboardButton(
            t('programs.kindergarten', lang),
            callback_data='program_kindergarten'
        )],
        [InlineKeyboardButton(
            t('programs.russian', lang),
            callback_data='program_russian'
        )],
        [InlineKeyboardButton(
            t('programs.ib', lang),
            callback_data='program_ib'
        )],
        [InlineKeyboardButton(
            t('programs.consultation', lang),
            callback_data='program_consultation'
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        t('program_interest', lang),
        reply_markup=reply_markup
    )


async def program_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle program selection and ask enrollment date"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    program = query.data.split('_')[1]  # program_ib -> ib
    db.set_user_data(chat_id, 'program', program)

    # NEW STEP: Ask Enrollment Date
    db.set_user_state(chat_id, 'awaiting_enrollment')
    await ask_enrollment_date(query, chat_id, lang)


async def ask_enrollment_date(query, chat_id: int, lang: str):
    """Ask when they plan to enroll"""
    # Localized texts for question and buttons
    texts = {
        'ru': {
            'question': "Когда вы планируете поступление?",
            'this_sem': "В этом семестре",
            'next_year': "В следующем учебном году (сентябрь 2026)",
            'exploring': "Пока просто изучаю варианты"
        },
        'en': {
            'question': "When are you planning to enroll?",
            'this_sem': "This semester",
            'next_year': "Next academic year (September 2026)",
            'exploring': "Just exploring for now"
        },
        'uz': {
            'question': "Qachon o'qishga kirishni rejalashtirmoqdasiz?",
            'this_sem': "Shu semestrda",
            'next_year': "Keyingi o'quv yilida (2026-yil Avgust)",
            'exploring': "Hozircha faqat tanishib chiqyapman"
        },
        'tr': {
            'question': "Ne zaman kayıt yaptırmayı planlıyorsunuz?",
            'this_sem': "Bu dönem için",
            'next_year': "Gelecek eğitim yılı (2026–2027, Eylül)",
            'exploring': "Şimdilik sadece bilgi alıyorum"
        }
    }
    
    t_data = texts.get(lang, texts['en'])
    
    keyboard = [
        [InlineKeyboardButton(t_data['this_sem'], callback_data='enroll_this_sem')],
        [InlineKeyboardButton(t_data['next_year'], callback_data='enroll_next_year')],
        [InlineKeyboardButton(t_data['exploring'], callback_data='enroll_exploring')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        t_data['question'],
        reply_markup=reply_markup
    )


async def enrollment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle enrollment date selection and create lead"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    enrollment = query.data.split('enroll_')[1] # this_sem, next_year, exploring
    db.set_user_data(chat_id, 'enrollment', enrollment)

    # Feature 4: Handoff to Admissions
    # Create lead in Kommo
    phone = db.get_user_data(chat_id, 'phone')
    name = db.get_user_data(chat_id, 'name', 'Unknown')
    contact_id = db.get_user_data(chat_id, 'contact_id')

    lead_data = {
        'name': name,
        'children_count': db.get_user_data(chat_id, 'children_count'),
        'children_ages': db.get_user_data(chat_id, 'children_ages'),
        'program': db.get_user_data(chat_id, 'program'),
        'enrollment': enrollment
    }

    # Update contact name first if needed
    if contact_id:
        kommo.update_contact_name(contact_id, name)

    lead_id = kommo.create_lead(contact_id, phone, lead_data)

    if lead_id:
        db.save_lead(chat_id, contact_id, lead_id)

        # Create task for admissions with summary
        summary = (
            f"New lead from Telegram - Call within 1 hour\n"
            f"Name: {name}\n"
            f"Phone: {phone}\n"
            f"Language: {lang}\n"
            f"Children: {lead_data['children_count']} ({', '.join(lead_data['children_ages'])})\n"
            f"Program: {lead_data['program']}\n"
            f"Enrollment: {enrollment}"
        )
        
        # Add summary as a note too
        kommo.add_note(lead_id, f"📝 LEAD SUMMARY:\n{summary}")
        
        kommo.create_task(lead_id, summary)

        # Notify admissions
        await notify_admissions(context, chat_id, phone, lang, lead_data)

    # Send handoff message with channel
    handoff_text = t('handoff', lang, phone=config.CONTACT_PHONE)

    keyboard = [[InlineKeyboardButton(
        '📢 ' + t('menu_buttons.channel', lang),
        url=config.CHANNEL_LINK
    )]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(handoff_text, reply_markup=reply_markup)

    # Set user to ready state
    db.set_user_state(chat_id, 'ready')


async def notify_admissions(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                            phone: str, lang: str, lead_data: dict):
    """Notify admissions team about new lead"""
    if not config.ADMISSIONS_CHAT_ID:
        return

    message = f"""🆕 New Lead from Telegram Bot

📞 Phone: {phone}
🌐 Language: {lang}
👶 Children: {lead_data.get('children_count', 'N/A')}
📅 Ages: {', '.join(lead_data.get('children_ages', []))}
📚 Program: {lead_data.get('program', 'N/A')}

💬 Chat ID: {chat_id}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📋 Action: Call within 1 hour"""

    try:
        await context.bot.send_message(
            chat_id=config.ADMISSIONS_CHAT_ID,
            text=message
        )
    except Exception as e:
        logger.error(f"Failed to notify admissions: {e}")


# Feature 5: Tour Booking
async def book_tour_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start tour booking process"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    # Check if user has phone
    if not db.get_user_data(chat_id, 'phone'):
        await query.message.reply_text(t('welcome', lang))
        db.set_user_state(chat_id, 'awaiting_phone')
        return

    db.set_user_state(chat_id, 'booking_tour_campus')
    await select_campus(query, chat_id, lang)


async def select_campus(query, chat_id: int, lang: str):
    """Select campus for tour"""
    keyboard = [
        [InlineKeyboardButton(
            config.CAMPUSES['mu']['name'][lang],
            callback_data='campus_mu'
        )],
        [InlineKeyboardButton(
            config.CAMPUSES['yashnobod']['name'][lang],
            callback_data='campus_yashnobod'
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        t('select_campus', lang),
        reply_markup=reply_markup
    )


async def campus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle campus selection"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    campus = query.data.split('_')[1]  # campus_mu -> mu
    db.set_user_data(chat_id, 'tour_campus', campus)

    db.set_user_state(chat_id, 'booking_tour_date')
    await select_date(query, chat_id, lang)


async def select_date(query, chat_id: int, lang: str, week_offset: int = 0):
    """Select date for tour"""
    # Generate next 7 days (Mon, Wed, Fri only)
    dates = []
    current = datetime.now() + timedelta(days=week_offset * 7)

    for i in range(14):  # Check 2 weeks
        date = current + timedelta(days=i)
        # Only Mon (0), Wed (2), Fri (4)
        if date.weekday() in [0, 2, 4]:
            dates.append(date)
        if len(dates) >= 3:
            break

    keyboard = []
    for date in dates:
        # Format: "Mon, 23 Dec"
        day_names = {
            'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
            'uz': ['Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan', 'Yak'],
            'en': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            'tr': ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
        }
        month_names = {
            'ru': ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
            'uz': ['yan', 'fev', 'mar', 'apr', 'may', 'iyun', 'iyul', 'avg', 'sen', 'okt', 'noy', 'dek'],
            'en': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            'tr': ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
        }

        day_name = day_names[lang][date.weekday()]
        month_name = month_names[lang][date.month - 1]
        label = f"{day_name}, {date.day} {month_name}"

        keyboard.append([InlineKeyboardButton(
            label,
            callback_data=f"date_{date.strftime('%Y-%m-%d')}"
        )])

    # Add "Next week" button
    if week_offset == 0:
        keyboard.append([InlineKeyboardButton(
            t('next_week', lang),
            callback_data='date_next_week'
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        t('select_date', lang),
        reply_markup=reply_markup
    )


async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date selection"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    data = query.data.split('_', 1)[1]  # date_2024-12-25 -> 2024-12-25

    if data == 'next_week':
        # Show next week
        await select_date(query, chat_id, lang, week_offset=1)
        return

    date = data
    db.set_user_data(chat_id, 'tour_date', date)

    db.set_user_state(chat_id, 'booking_tour_time')
    await select_time(query, chat_id, lang)


async def select_time(query, chat_id: int, lang: str):
    """Select time for tour"""
    keyboard = []
    for time in config.TOUR_TIMES:
        keyboard.append([InlineKeyboardButton(
            time,
            callback_data=f"time_{time}"
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        t('select_time', lang),
        reply_markup=reply_markup
    )


async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time selection and confirm tour"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    time = query.data.split('_')[1]  # time_14:00 -> 14:00
    db.set_user_data(chat_id, 'tour_time', time)

    # Create tour booking
    phone = db.get_user_data(chat_id, 'phone')
    campus = db.get_user_data(chat_id, 'tour_campus')
    date = db.get_user_data(chat_id, 'tour_date')

    tour = db.create_tour(chat_id, phone, campus, date, time, lang)

    # Update Kommo
    lead = db.get_lead(chat_id)
    if lead:
        kommo.update_lead(lead['lead_id'], {
            'tour_campus': campus,
            'tour_date': date,
            'tour_time': time,
            'tour_status': 'booked'
        })

    # Send confirmation
    campus_info = config.CAMPUSES[campus]
    campus_name = campus_info['name'][lang]

    # Format date nicely
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    day_names = {
        'ru': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        'uz': ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'],
        'en': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        'tr': ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
    }
    month_names = {
        'ru': ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
               'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
        'uz': ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
               'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
        'en': ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December'],
        'tr': ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
               'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
    }

    formatted_date = f"{day_names[lang][date_obj.weekday()]}, {date_obj.day} {month_names[lang][date_obj.month - 1]}"

    confirmation = t('tour_confirmed', lang,
                    campus=campus_name,
                    date=formatted_date,
                    time=time,
                    address=campus_info['address'],
                    map=campus_info['map'])

    await query.edit_message_text(confirmation)

    # Notify admissions
    if config.ADMISSIONS_CHAT_ID:
        await context.bot.send_message(
            chat_id=config.ADMISSIONS_CHAT_ID,
            text=f"📅 New Tour Booking\n\n"
                 f"Phone: {phone}\n"
                 f"Campus: {campus_name}\n"
                 f"Date: {formatted_date}\n"
                 f"Time: {time}\n"
                 f"Language: {lang}"
        )

    db.set_user_state(chat_id, 'ready')


# Feature 8: Menu
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu"""
    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    keyboard = [
        [InlineKeyboardButton(
            t('menu_buttons.book_tour', lang),
            callback_data='menu_book_tour'
        )],
        [InlineKeyboardButton(
            t('menu_buttons.addresses', lang),
            callback_data='menu_addresses'
        )],
        [InlineKeyboardButton(
            t('menu_buttons.contact_manager', lang),
            callback_data='menu_contact_manager'
        )],
        [InlineKeyboardButton(
            t('menu_buttons.channel', lang),
            url=config.CHANNEL_LINK
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = t('menu', lang)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu selections"""
    query = update.callback_query
    await query.answer()

    action = query.data.split('_', 1)[1]  # menu_book_tour -> book_tour

    if action == 'book_tour':
        await book_tour_callback(update, context)
    elif action == 'addresses':
        await show_addresses(update, context)
    elif action == 'contact_manager':
        await contact_manager(update, context)


async def show_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show campus addresses"""
    query = update.callback_query
    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    text = t('campus_addresses', lang)

    for campus_key, campus_info in config.CAMPUSES.items():
        text += f"📍 {campus_info['name'][lang]}\n"
        text += f"{campus_info['address']}\n"
        text += f"🗺 {campus_info['map']}\n\n"

    await query.edit_message_text(text)


async def contact_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User wants to contact manager"""
    query = update.callback_query
    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    # Notify admissions
    phone = db.get_user_data(chat_id, 'phone', 'Not provided')

    if config.ADMISSIONS_CHAT_ID:
        await context.bot.send_message(
            chat_id=config.ADMISSIONS_CHAT_ID,
            text=f"💬 User wants to contact manager\n\n"
                 f"Phone: {phone}\n"
                 f"Chat ID: {chat_id}\n"
                 f"Language: {lang}\n"
                 f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

    await query.edit_message_text(t('manager_will_contact', lang))


# Handle text messages (for menu shortcuts)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    text = update.message.text.lower()

    # Check for menu command
    if text in ['меню', 'menu', 'menyu']:
        await menu_command(update, context)
        return

    # Otherwise check state
    chat_id = update.effective_chat.id
    user = db.get_user(chat_id)

    if not user:
        return

    # If message is not part of flow, treat as chat message
    if user.get('state') == 'ready':
        await forward_to_kommo_chat(update, context)
        return

    # Handle Name Input
    if user.get('state') == 'awaiting_name':
        await handle_name(update, context)
        return

    # Handle Phone Input
    if user.get('state') == 'awaiting_phone':
        await handle_phone(update, context)
        return

    # If stuck in other states but typing text
    pass


# Callback query router
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route callback queries to appropriate handler"""
    query = update.callback_query
    data = query.data

    if data.startswith('lang_'):
        await language_callback(update, context)
    elif data.startswith('children_'):
        await children_count_callback(update, context)
    elif data.startswith('age_'):
        await child_age_callback(update, context)
    elif data.startswith('program_'):
        await program_callback(update, context)
    elif data.startswith('enroll_'):
        await enrollment_callback(update, context)
    elif data.startswith('campus_'):
        await campus_callback(update, context)
    elif data.startswith('date_'):
        await date_callback(update, context)
    elif data.startswith('time_'):
        await time_callback(update, context)
    elif data.startswith('menu_'):
        await menu_callback(update, context)
    elif data.startswith('reminder_'):
        await reminder_callback(update, context)
    elif data.startswith('admin_status_'):
        await admin_status_callback(update, context)
    else:
        await query.answer("Unknown action")


# Feature 6 & 7: Tour reminder and follow-up callbacks
async def reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle tour reminder responses"""
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang = get_user_lang(chat_id)

    action = query.data.split('_')[1]  # reminder_confirm -> confirm

    # Find active tour for user
    tours = db.get_user_tours(chat_id)
    active_tour = None
    for tour in tours:
        if tour['status'] == 'booked':
            active_tour = tour
            break

    if not active_tour:
        await query.edit_message_text("Tour not found")
        return

    if action == 'confirm':
        db.update_tour(active_tour['id'], status='confirmed')
        await query.edit_message_text(
            "✅ " + t('reminder_buttons.confirm', lang)
        )
    elif action in ['reschedule', 'cancel']:
        db.update_tour(active_tour['id'], status='cancelled')
        await query.edit_message_text(
            t('reschedule_message', lang)
        )

        # Notify admissions
        if config.ADMISSIONS_CHAT_ID:
            phone = db.get_user_data(chat_id, 'phone')
            await context.bot.send_message(
                chat_id=config.ADMISSIONS_CHAT_ID,
                text=f"🔄 Tour {'Reschedule' if action == 'reschedule' else 'Cancellation'}\n\n"
                     f"Phone: {phone}\n"
                     f"Tour: {active_tour['date']} {active_tour['time']}\n"
                     f"Campus: {active_tour['campus']}"
            )


# Admin callback for tour status updates
async def admin_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin tour status updates"""
    query = update.callback_query
    await query.answer()

    # Parse callback data: admin_status_{tour_id}_{status}
    parts = query.data.split('_')
    tour_id = int(parts[2])
    status = parts[3]  # attended, noshow, rescheduled

    # Update tour status
    db.update_tour(tour_id, status=status)

    # Update in Kommo
    tour = db.get_tour(tour_id)
    if tour:
        lead = db.get_lead(tour['chat_id'])
        if lead:
            kommo.update_lead(lead['lead_id'], {'tour_status': status})

    await query.edit_message_text(
        f"✅ Tour status updated to: {status}\n\n"
        f"{query.message.text}"
    )


async def forward_to_kommo_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward user message to amoCRM as a note"""
    chat_id = update.effective_chat.id
    text = update.message.text
    user_name = update.effective_user.full_name
    
    # Get active lead
    lead = db.get_lead(chat_id)
    if not lead:
        logger.warning(f"No active lead for chat {chat_id}, cannot attach note")
        return

    # Add note to lead
    note_text = f"📩 Сообщение от {user_name} (Telegram):\n{text}"
    success = kommo.add_note(lead['lead_id'], note_text)
    
    if not success:
        logger.error(f"Failed to add note for lead {lead['lead_id']}")

async def webhook_server(application: Application):
    """Run aiohttp server for amoCRM webhooks"""
    from aiohttp import web
    import json

    async def handle_webhook(request):
        try:
            # Read raw body (consume stream)
            await request.read()
            
            # Parse post data
            data = await request.post()
            
            # Iterate keys to find note text
            for key in data.keys():
                # We look for keys like 'leads[note][0][note][text]'
                # The raw key string contains the full path
                if 'note' in key and '[text]' in key:
                    note_text = data[key]
                    
                    # Check for manager reply prefix
                    if note_text.startswith('>>>') or note_text.startswith('!'):
                        reply_text = note_text[3:].strip() if note_text.startswith('>>>') else note_text[1:].strip()
                        
                        # Find corresponding element_id (Lead ID)
                        # Replace [text] with [element_id] in the key
                        # Example key: leads[note][0][note][text]
                        # Target key: leads[note][0][note][element_id]
                        lead_id_key = key.replace('[text]', '[element_id]')
                        lead_id = data.get(lead_id_key)
                        
                        if lead_id:
                             logger.info(f"Found reply for Lead {lead_id}: {reply_text}")
                             chat_id = db.get_chat_id_by_lead(int(lead_id))
                             
                             if chat_id:
                                 await application.bot.send_message(chat_id=chat_id, text=reply_text)
                                 logger.info(f"Sent reply to Chat {chat_id}")
                                 return web.Response(text="OK")
                             else:
                                 logger.warning(f"Chat ID not found for Lead {lead_id}")

            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return web.Response(status=500)

    app = web.Application()
    app.router.add_post('/kommo-webhook', handle_webhook)
    
    port = config.PORT
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    public_base = config.PUBLIC_BASE_URL
    if public_base:
        logger.info(f"👉 Set this URL in amoCRM (Custom Integration -> Webhook): {public_base}/kommo-webhook")
    else:
        from pyngrok import ngrok
        ngrok_token = config.NGROK_AUTH_TOKEN
        if ngrok_token:
            ngrok.set_auth_token(ngrok_token)
        public_url = ngrok.connect(port).public_url
        logger.info(f"🚀 Ngrok Tunnel Started: {public_url}")
        logger.info(f"👉 Set this URL in amoCRM (Custom Integration -> Webhook): {public_url}/kommo-webhook")


async def post_init(application: Application):
    """Setup scheduler and webhook server after application start"""
    scheduler = setup_scheduler(application.bot)
    scheduler.start()
    logger.info("Scheduler started")
    
    # Start webhook server for Chat API
    await webhook_server(application)


def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Start bot
    logger.info("Bot started with automated reminders enabled")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
