import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, DateTime, JSON, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import config

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    chat_id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    language = Column(String, default='ru')
    state = Column(String, default='start')
    data = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Tour(Base):
    __tablename__ = 'tours'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    phone = Column(String)
    campus = Column(String)
    date = Column(String)
    time = Column(String)
    language = Column(String)
    status = Column(String, default='booked')
    reminder_sent = Column(Integer, default=0) # Using Integer as boolean (0/1) for simplicity or Boolean type
    followup_sent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Database:
    """PostgreSQL database for bot state"""
    
    def __init__(self):
        self.engine = None
        self.Session = None
        
        db_url = config.DATABASE_URL
        if db_url:
            try:
                self.engine = create_engine(db_url)
                Base.metadata.create_all(self.engine)
                self.Session = sessionmaker(bind=self.engine)
                logger.info("Connected to PostgreSQL database")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
        else:
            logger.error("DATABASE_URL not found in config")

    def _get_session(self):
        if not self.Session:
            return None
        return self.Session()

    # User methods
    def get_user(self, chat_id: int) -> Optional[Dict]:
        """Get user data"""
        session = self._get_session()
        if not session: return None
        try:
            user = session.query(User).filter_by(chat_id=chat_id).first()
            if user:
                return {
                    'chat_id': user.chat_id,
                    'username': user.username,
                    'language': user.language,
                    'state': user.state,
                    'data': user.data or {},
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
            return None
        finally:
            session.close()

    def create_user(self, chat_id: int, username: str = None, language: str = None) -> Dict:
        """Create or update user"""
        session = self._get_session()
        if not session: return {}
        try:
            user = session.query(User).filter_by(chat_id=chat_id).first()
            if not user:
                user = User(
                    chat_id=chat_id,
                    username=username,
                    language=language or 'ru',
                    state='start',
                    data={}
                )
                session.add(user)
            else:
                if language:
                    user.language = language
                if username:
                    user.username = username
            
            session.commit()
            return {
                'chat_id': user.chat_id,
                'username': user.username,
                'language': user.language,
                'state': user.state,
                'data': user.data or {},
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            session.rollback()
            return {}
        finally:
            session.close()

    def update_user(self, chat_id: int, **kwargs):
        """Update user data"""
        session = self._get_session()
        if not session: return
        try:
            user = session.query(User).filter_by(chat_id=chat_id).first()
            if not user:
                user = User(chat_id=chat_id)
                session.add(user)
            
            for key, value in kwargs.items():
                if key == 'data':
                    # Merge data dict
                    current_data = dict(user.data) if user.data else {}
                    current_data.update(value)
                    user.data = current_data
                elif hasattr(user, key):
                    setattr(user, key, value)
            
            session.commit()
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            session.rollback()
        finally:
            session.close()

    def set_user_state(self, chat_id: int, state: str):
        """Set user state"""
        self.update_user(chat_id, state=state)

    def get_user_language(self, chat_id: int) -> str:
        """Get user language"""
        user = self.get_user(chat_id)
        return user['language'] if user else 'ru'

    def set_user_data(self, chat_id: int, key: str, value):
        """Set user data field"""
        session = self._get_session()
        if not session: return
        try:
            user = session.query(User).filter_by(chat_id=chat_id).first()
            if not user:
                user = User(chat_id=chat_id)
                session.add(user)
            
            current_data = dict(user.data) if user.data else {}
            current_data[key] = value
            user.data = current_data
            
            session.commit()
        except Exception as e:
            logger.error(f"Error setting user data: {e}")
            session.rollback()
        finally:
            session.close()

    def get_user_data(self, chat_id: int, key: str, default=None):
        """Get user data field"""
        user = self.get_user(chat_id)
        if user and user.get('data'):
            return user['data'].get(key, default)
        return default
        
    def get_total_users(self) -> int:
        """Get total number of users who started the bot"""
        session = self._get_session()
        if not session: return 0
        try:
            return session.query(User).count()
        finally:
            session.close()

    def get_all_users(self) -> List[int]:
        """Get all user chat IDs"""
        session = self._get_session()
        if not session: return []
        try:
            users = session.query(User.chat_id).all()
            return [u[0] for u in users]
        finally:
            session.close()

    # Tour methods
    def create_tour(self, chat_id: int, phone: str, campus: str,
                    date: str, time: str, language: str) -> Dict:
        """Create a tour booking"""
        session = self._get_session()
        if not session: return {}
        try:
            tour = Tour(
                chat_id=chat_id,
                phone=phone,
                campus=campus,
                date=date,
                time=time,
                language=language,
                status='booked'
            )
            session.add(tour)
            session.commit()
            
            return {
                'id': tour.id,
                'chat_id': tour.chat_id,
                'phone': tour.phone,
                'campus': tour.campus,
                'date': tour.date,
                'time': tour.time,
                'language': tour.language,
                'status': tour.status,
                'created_at': tour.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error creating tour: {e}")
            session.rollback()
            return {}
        finally:
            session.close()

    def get_tour(self, tour_id: int) -> Optional[Dict]:
        """Get tour by ID"""
        session = self._get_session()
        if not session: return None
        try:
            tour = session.query(Tour).filter_by(id=tour_id).first()
            if tour:
                return {
                    'id': tour.id,
                    'chat_id': tour.chat_id,
                    'phone': tour.phone,
                    'campus': tour.campus,
                    'date': tour.date,
                    'time': tour.time,
                    'language': tour.language,
                    'status': tour.status,
                    'reminder_sent': bool(tour.reminder_sent),
                    'followup_sent': bool(tour.followup_sent),
                    'created_at': tour.created_at.isoformat()
                }
            return None
        finally:
            session.close()

    def get_user_tours(self, chat_id: int) -> List[Dict]:
        """Get all tours for user"""
        session = self._get_session()
        if not session: return []
        try:
            tours = session.query(Tour).filter_by(chat_id=chat_id).all()
            return [{
                'id': t.id,
                'chat_id': t.chat_id,
                'phone': t.phone,
                'campus': t.campus,
                'date': t.date,
                'time': t.time,
                'status': t.status
            } for t in tours]
        finally:
            session.close()

    def update_tour(self, tour_id: int, **kwargs):
        """Update tour"""
        session = self._get_session()
        if not session: return False
        try:
            tour = session.query(Tour).filter_by(id=tour_id).first()
            if tour:
                for key, value in kwargs.items():
                    if hasattr(tour, key):
                        setattr(tour, key, value)
                session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating tour: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_tours_needing_reminder(self) -> List[Dict]:
        """Get tours that need reminder (tomorrow, not yet sent)"""
        session = self._get_session()
        if not session: return []
        try:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            tours = session.query(Tour).filter(
                Tour.date == tomorrow,
                Tour.status == 'booked',
                (Tour.reminder_sent == 0) | (Tour.reminder_sent == None)
            ).all()
            
            return [{
                'id': t.id,
                'chat_id': t.chat_id,
                'phone': t.phone,
                'campus': t.campus,
                'date': t.date,
                'time': t.time,
                'language': t.language
            } for t in tours]
        finally:
            session.close()

    def get_tours_for_followup(self) -> List[Dict]:
        """Get tours that need follow-up (yesterday, status = attended)"""
        session = self._get_session()
        if not session: return []
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            tours = session.query(Tour).filter(
                Tour.date == yesterday,
                Tour.status == 'attended',
                (Tour.followup_sent == 0) | (Tour.followup_sent == None)
            ).all()
            
            return [{
                'id': t.id,
                'chat_id': t.chat_id,
                'phone': t.phone,
                'campus': t.campus,
                'date': t.date,
                'time': t.time,
                'language': t.language
            } for t in tours]
        finally:
            session.close()

    # Global database instance
db = Database()
