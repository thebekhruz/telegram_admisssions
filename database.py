import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DB_FILE = 'bot_data.json'


class Database:
    """Simple JSON-based database for bot state"""

    def __init__(self):
        self.data = self._load()

    def _load(self) -> Dict:
        """Load database from file"""
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading database: {e}")

        return {
            'users': {},
            'tours': [],
            'leads': {}
        }

    def _save(self):
        """Save database to file"""
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving database: {e}")

    # User methods
    def get_user(self, chat_id: int) -> Optional[Dict]:
        """Get user data"""
        return self.data['users'].get(str(chat_id))

    def create_user(self, chat_id: int, language: str = None) -> Dict:
        """Create or update user"""
        user_data = {
            'chat_id': chat_id,
            'language': language or 'ru',
            'state': 'start',
            'data': {},
            'created_at': datetime.now().isoformat()
        }
        self.data['users'][str(chat_id)] = user_data
        self._save()
        return user_data

    def update_user(self, chat_id: int, **kwargs):
        """Update user data"""
        user = self.get_user(chat_id)
        if not user:
            user = self.create_user(chat_id)

        for key, value in kwargs.items():
            if key == 'data':
                # Merge data dict
                user['data'].update(value)
            else:
                user[key] = value

        user['updated_at'] = datetime.now().isoformat()
        self._save()

    def set_user_state(self, chat_id: int, state: str):
        """Set user state"""
        self.update_user(chat_id, state=state)

    def get_user_language(self, chat_id: int) -> str:
        """Get user language"""
        user = self.get_user(chat_id)
        return user['language'] if user else 'ru'

    def set_user_data(self, chat_id: int, key: str, value):
        """Set user data field"""
        user = self.get_user(chat_id)
        if not user:
            user = self.create_user(chat_id)
        user['data'][key] = value
        self._save()

    def get_user_data(self, chat_id: int, key: str, default=None):
        """Get user data field"""
        user = self.get_user(chat_id)
        if user:
            return user['data'].get(key, default)
        return default

    # Tour methods
    def create_tour(self, chat_id: int, phone: str, campus: str,
                    date: str, time: str, language: str) -> Dict:
        """Create a tour booking"""
        tour = {
            'id': len(self.data['tours']) + 1,
            'chat_id': chat_id,
            'phone': phone,
            'campus': campus,
            'date': date,
            'time': time,
            'language': language,
            'status': 'booked',
            'reminder_sent': False,
            'created_at': datetime.now().isoformat()
        }
        self.data['tours'].append(tour)
        self._save()
        return tour

    def get_tour(self, tour_id: int) -> Optional[Dict]:
        """Get tour by ID"""
        for tour in self.data['tours']:
            if tour['id'] == tour_id:
                return tour
        return None

    def get_user_tours(self, chat_id: int) -> List[Dict]:
        """Get all tours for user"""
        return [t for t in self.data['tours'] if t['chat_id'] == chat_id]

    def update_tour(self, tour_id: int, **kwargs):
        """Update tour"""
        for tour in self.data['tours']:
            if tour['id'] == tour_id:
                tour.update(kwargs)
                tour['updated_at'] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def get_tours_needing_reminder(self) -> List[Dict]:
        """Get tours that need reminder (tomorrow, not yet sent)"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        tours = []

        for tour in self.data['tours']:
            if (tour['date'] == tomorrow and
                tour['status'] == 'booked' and
                not tour.get('reminder_sent', False)):
                tours.append(tour)

        return tours

    def get_tours_for_followup(self) -> List[Dict]:
        """Get tours that need follow-up (yesterday, status = attended)"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        tours = []

        for tour in self.data['tours']:
            if (tour['date'] == yesterday and
                tour['status'] == 'attended' and
                not tour.get('followup_sent', False)):
                tours.append(tour)

        return tours

    # Lead methods
    def save_lead(self, chat_id: int, contact_id: int, lead_id: int):
        """Save lead IDs for user"""
        self.data['leads'][str(chat_id)] = {
            'contact_id': contact_id,
            'lead_id': lead_id,
            'created_at': datetime.now().isoformat()
        }
        self._save()

    def get_lead(self, chat_id: int) -> Optional[Dict]:
        """Get lead IDs for user"""
        return self.data['leads'].get(str(chat_id))

    def get_chat_id_by_lead(self, lead_id: int) -> Optional[int]:
        """Get Telegram chat ID by amoCRM lead ID"""
        for chat_id, lead_data in self.data['leads'].items():
            if lead_data.get('lead_id') == lead_id:
                return int(chat_id)
        return None


# Global database instance
db = Database()
