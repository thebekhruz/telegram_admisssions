"""
Automated scheduler for tour reminders and follow-ups
"""
import logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from database import db
from kommo import KommoAPI
from translations import t

logger = logging.getLogger(__name__)
kommo = KommoAPI()


async def send_tour_reminders(bot):
    """
    Feature 6: Send tour reminders
    Runs daily to check for tours tomorrow and send reminders
    """
    logger.info("Checking for tours needing reminders...")

    tours = db.get_tours_needing_reminder()

    for tour in tours:
        try:
            chat_id = tour['chat_id']
            lang = tour['language']
            campus = tour['campus']
            date = tour['date']
            time = tour['time']

            # Get campus info
            campus_info = config.CAMPUSES[campus]
            campus_name = campus_info['name'][lang]

            # Format date
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

            formatted_date = f"{date_obj.day} {month_names[lang][date_obj.month - 1]}"

            # Build reminder message
            reminder_text = t('tour_reminder', lang,
                            campus=campus_name,
                            date=formatted_date,
                            time=time,
                            address=campus_info['address'],
                            map=campus_info['map'])

            # Add action buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        t('reminder_buttons.confirm', lang),
                        callback_data='reminder_confirm'
                    ),
                    InlineKeyboardButton(
                        t('reminder_buttons.reschedule', lang),
                        callback_data='reminder_reschedule'
                    )
                ],
                [
                    InlineKeyboardButton(
                        t('reminder_buttons.cancel', lang),
                        callback_data='reminder_cancel'
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send reminder
            await bot.send_message(
                chat_id=chat_id,
                text=reminder_text,
                reply_markup=reply_markup
            )

            # Mark as sent
            db.update_tour(tour['id'], reminder_sent=True)

            logger.info(f"Sent reminder for tour {tour['id']}")

        except Exception as e:
            logger.error(f"Error sending reminder for tour {tour['id']}: {e}")

    logger.info(f"Sent {len(tours)} tour reminders")


async def send_post_tour_followups(bot):
    """
    Feature 7: Send post-tour follow-ups
    Runs daily to check for tours that happened yesterday (status = attended)
    """
    logger.info("Checking for tours needing follow-up...")

    tours = db.get_tours_for_followup()

    for tour in tours:
        try:
            chat_id = tour['chat_id']
            lang = tour['language']

            # Build follow-up message
            followup_text = t('post_tour_followup', lang)

            keyboard = [[InlineKeyboardButton(
                t('contact_manager_notification', lang),
                callback_data='menu_contact_manager'
            )]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send follow-up
            await bot.send_message(
                chat_id=chat_id,
                text=followup_text,
                reply_markup=reply_markup
            )

            # Mark as sent
            db.update_tour(tour['id'], followup_sent=True)

            logger.info(f"Sent follow-up for tour {tour['id']}")

        except Exception as e:
            logger.error(f"Error sending follow-up for tour {tour['id']}: {e}")

    logger.info(f"Sent {len(tours)} post-tour follow-ups")


async def check_tour_status_updates(bot):
    """
    Check for tours that need status updates and notify admissions
    This helps implement the hybrid approach where bot reminds admissions
    to update tour status
    """
    logger.info("Checking for tour status updates...")

    # Get tours from yesterday that don't have status updated
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    all_tours = db.data.get('tours', [])
    tours_needing_status = [
        t for t in all_tours
        if t['date'] == yesterday and t['status'] == 'booked'
    ]

    if not tours_needing_status or not config.ADMISSIONS_CHAT_ID:
        return

    # Send reminder to admissions
    for tour in tours_needing_status:
        phone = tour['phone']
        campus = tour['campus']
        time = tour['time']

        keyboard = [
            [
                InlineKeyboardButton(
                    '✅ Attended',
                    callback_data=f'admin_status_{tour["id"]}_attended'
                ),
                InlineKeyboardButton(
                    '❌ No-Show',
                    callback_data=f'admin_status_{tour["id"]}_noshow'
                )
            ],
            [
                InlineKeyboardButton(
                    '🔄 Rescheduled',
                    callback_data=f'admin_status_{tour["id"]}_rescheduled'
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await bot.send_message(
                chat_id=config.ADMISSIONS_CHAT_ID,
                text=f"📋 Tour Status Check\n\n"
                     f"Lead: {phone}\n"
                     f"Tour: Yesterday ({yesterday})\n"
                     f"Time: {time}\n"
                     f"Campus: {campus}\n\n"
                     f"Did they attend?",
                reply_markup=reply_markup
            )

            logger.info(f"Sent status check for tour {tour['id']}")

        except Exception as e:
            logger.error(f"Error sending status check for tour {tour['id']}: {e}")


def setup_scheduler(bot):
    """Setup automated scheduler"""
    scheduler = AsyncIOScheduler()

    # Send tour reminders daily at 10:00 AM
    scheduler.add_job(
        send_tour_reminders,
        CronTrigger(hour=10, minute=0),
        args=[bot],
        id='tour_reminders',
        name='Send tour reminders',
        replace_existing=True
    )

    # Send post-tour follow-ups daily at 11:00 AM
    scheduler.add_job(
        send_post_tour_followups,
        CronTrigger(hour=11, minute=0),
        args=[bot],
        id='post_tour_followups',
        name='Send post-tour follow-ups',
        replace_existing=True
    )

    # Check tour status daily at 12:00 PM
    scheduler.add_job(
        check_tour_status_updates,
        CronTrigger(hour=12, minute=0),
        args=[bot],
        id='tour_status_check',
        name='Check tour status updates',
        replace_existing=True
    )

    # scheduler.start()  # Moved to post_init in bot.py
    logger.info("Scheduler configured with jobs:")
    logger.info("  - Tour reminders: Daily at 10:00 AM")
    logger.info("  - Post-tour follow-ups: Daily at 11:00 AM")
    logger.info("  - Tour status checks: Daily at 12:00 PM")

    return scheduler
