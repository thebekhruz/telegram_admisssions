import requests
import config
from typing import Dict, Optional, List
import logging
import time
import json

logger = logging.getLogger(__name__)


class KommoAPI:
    """amoCRM API Integration (Kommo = amoCRM rebranded)"""

    def __init__(self):
        self.base_url = config.AMOCRM_API_URL
        self.access_token = config.AMOCRM_ACCESS_TOKEN
        self.refresh_token = config.AMOCRM_REFRESH_TOKEN
        self.client_id = config.AMOCRM_CLIENT_ID
        self.client_secret = config.AMOCRM_CLIENT_SECRET
        self.subdomain = config.AMOCRM_SUBDOMAIN
        self.domain = config.AMOCRM_DOMAIN
        self.token_expires_at = None
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        try:
            url = f"https://{self.subdomain}.{self.domain}/oauth2/access_token"
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "redirect_uri": "https://example.com"
            }

            response = requests.post(url, json=data)
            response.raise_for_status()

            tokens = response.json()
            self.access_token = tokens['access_token']
            self.refresh_token = tokens['refresh_token']
            self.token_expires_at = time.time() + tokens['expires_in']

            # Update headers
            self.headers['Authorization'] = f'Bearer {self.access_token}'

            # Save new tokens to file for persistence
            self._save_tokens(tokens)

            logger.info("amoCRM access token refreshed successfully")
            return True

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    def _save_tokens(self, tokens: dict):
        """Save refreshed tokens to file"""
        try:
            with open('.token_cache', 'w') as f:
                json.dump({
                    'access_token': tokens['access_token'],
                    'refresh_token': tokens['refresh_token'],
                    'expires_at': time.time() + tokens['expires_in']
                }, f)
        except Exception as e:
            logger.warning(f"Could not save tokens: {e}")

    def _ensure_token_valid(self):
        """Check if token needs refresh before API calls"""
        if self.token_expires_at and time.time() >= self.token_expires_at - 300:  # 5 min buffer
            logger.info("Token expiring soon, refreshing...")
            self.refresh_access_token()

    def _make_request(self, method: str, endpoint: str, **kwargs):
        """Make API request with automatic token refresh"""
        self._ensure_token_valid()

        url = f"{self.base_url}/{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)

        # If unauthorized, try refreshing token once
        if response.status_code == 401:
            logger.warning("Got 401, attempting token refresh...")
            if self.refresh_access_token():
                response = requests.request(method, url, headers=self.headers, **kwargs)

        return response

    def find_contact_by_phone(self, phone: str) -> Optional[Dict]:
        """Find contact in amoCRM by phone number"""
        try:
            response = self._make_request('GET', 'contacts', params={'query': phone})
            response.raise_for_status()

            data = response.json()
            if data.get('_embedded', {}).get('contacts'):
                return data['_embedded']['contacts'][0]
            return None
        except Exception as e:
            logger.error(f"Error finding contact: {e}")
            return None

    def create_or_update_contact(self, phone: str, name: str = None,
                                  chat_id: int = None, username: str = None, language: str = None) -> Optional[int]:
        """Create or update contact in amoCRM"""
        try:
            # Check if contact exists
            existing = self.find_contact_by_phone(phone)

            custom_fields = []

            # Add phone field (Standard WORK enum)
            custom_fields.append({
                'field_code': 'PHONE',
                'values': [{'value': phone, 'enum_code': 'WORK'}]
            })
            
            # Add "Контактный номер 1" (ID: 522485) as requested
            custom_fields.append({
                'field_id': 522485,
                'values': [{'value': phone}]
            })

            # Add Telegram chat_id
            if chat_id:
                custom_fields.append({
                    'field_id': 995929,  # Telegram ID
                    'values': [{'value': str(chat_id)}]
                })

            # Add Telegram Username
            if username:
                custom_fields.append({
                    'field_id': 995927,  # Telegram Username
                    'values': [{'value': username}]
                })

            # Add language preference
            if language:
                custom_fields.append({
                    'field_id': 995931,  # Язык общения
                    'values': [{'value': language}]
                })

            # Add Parent Name (ФИО Родителя) to Contact as well, if provided
            # User requested to use standard Name field, which is handled by contact_data['name'] below.
            # Removing duplicate mapping to custom field 985897 unless explicitly required again.
            # if name and name != 'Unknown':
            #     custom_fields.append({
            #         'field_id': 985897,  # ФИО Родителя
            #         'values': [{'value': name}]
            #     })

            contact_data = {
                'custom_fields_values': custom_fields
            }

            if name:
                contact_data['name'] = name

            if existing:
                # Update existing contact
                contact_id = existing['id']
                response = self._make_request('PATCH', f'contacts/{contact_id}', json=contact_data)
            else:
                # Create new contact
                response = self._make_request('POST', 'contacts', json=[contact_data])

            response.raise_for_status()
            result = response.json()

            if existing:
                return contact_id
            else:
                return result['_embedded']['contacts'][0]['id']

        except Exception as e:
            logger.error(f"Error creating/updating contact: {e}")
            return None

    def update_contact_name(self, contact_id: int, name: str) -> bool:
        """Update contact name"""
        try:
            data = {
                "name": name
            }
            response = self._make_request('PATCH', f'contacts/{contact_id}', json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error updating contact name: {e}")
            return False

    def create_lead(self, contact_id: int, phone: str, data: Dict) -> Optional[int]:
        """Create a lead in amoCRM"""
        try:
            # Build custom fields
            custom_fields = []

            # Children count (Количество детей - 995937)
            if 'children_count' in data:
                custom_fields.append({
                    'field_id': 995937,
                    'values': [{'value': str(data['children_count'])}]
                })

            # Children ages (Возраст детей - 991841)
            if 'children_ages' in data:
                custom_fields.append({
                    'field_id': 991841,
                    'values': [{'value': ', '.join(data['children_ages'])}]
                })

            # Program interest (Интересующая программа - 995887)
            if 'program' in data:
                # Need to map program values to enum IDs
                program_enums = {
                    'kindergarten': 1222831,  # Kindergarden
                    'russian_school': 1222833, # Russian School
                    'ib_school': 1222835,      # IB School
                    'consultation': 1222837    # Consultation
                }
                
                # Get the enum ID, defaulting to Consultation if not found
                program_key = data['program'].lower().replace(' ', '_')
                enum_id = program_enums.get(program_key)
                
                # Try partial matching if direct key lookup fails
                if not enum_id:
                    if 'kinder' in program_key: enum_id = 1222831
                    elif 'russian' in program_key: enum_id = 1222833
                    elif 'ib' in program_key: enum_id = 1222835
                    else: enum_id = 1222837

                custom_fields.append({
                    'field_id': 995887,
                    'values': [{'enum_id': enum_id}]
                })

            # Enrollment Date (Когда планирует поступление - 995907)
            if 'enrollment' in data:
                # Map keys from bot to Enums
                # this_sem -> 1222871 (В этом семестре)
                # next_year -> 1222873 (В следующем учебном году)
                # exploring -> 1222875 (Пока просто изучает варианты)
                
                enroll_enums = {
                    'enroll_this_sem': 1222871,
                    'enroll_next_year': 1222873,
                    'enroll_exploring': 1222875
                }
                # Handle raw keys if they come without prefix
                key = data['enrollment']
                if not key.startswith('enroll_'):
                    key = 'enroll_' + key
                    
                enum_id = enroll_enums.get(key)
                
                if enum_id:
                    custom_fields.append({
                        'field_id': 995907,
                        'values': [{'enum_id': enum_id}]
                    })
                
                # ALSO FILL: Срок поступления (Text field - 995943) as requested
                enroll_text_map = {
                    'enroll_this_sem': 'В этом семестре',
                    'enroll_next_year': 'В следующем учебном году',
                    'enroll_exploring': 'Пока просто изучает варианты'
                }
                text_val = enroll_text_map.get(key, key)
                custom_fields.append({
                    'field_id': 995943,
                    'values': [{'value': text_val}]
                })

            # Tour details
            if 'tour_campus' in data:
                # Campus field ID: 982191
                # MU Campus: 1211167
                # Yashnobod Campus: 1211169
                campus_enum = 1211167 if 'mu' in data['tour_campus'].lower() else 1211169
                
                custom_fields.append({
                    'field_id': 982191,
                    'values': [{'enum_id': campus_enum}]
                })

            if 'tour_date' in data:
                # Using TEST 3 for date/time combo - 991845
                date_time = f"{data.get('tour_date', '')} {data.get('tour_time', '')}"
                custom_fields.append({
                    'field_id': 991845,
                    'values': [{'value': date_time}]
                })
            
            # Prepare lead data
            lead_name = f"Telegram Lead - {phone}"
            if 'name' in data and data['name'] != 'Unknown':
                lead_name = f"{data['name']} - {phone}"
                
                # Removed mapping to 985897 as per user request to use standard contact name
                # and "Contact Phone 1" in contact card.
                
            lead_data = {
                'name': lead_name,
                'custom_fields_values': custom_fields,
            }
            
            # Attach contact only if ID is valid
            if contact_id:
                lead_data['_embedded'] = {
                    'contacts': [{'id': int(contact_id)}]
                }

            # Add pipeline and status if configured
            if config.AMOCRM_PIPELINE_ID:
                lead_data['pipeline_id'] = config.AMOCRM_PIPELINE_ID
            
            if config.AMOCRM_STATUS_ID:
                lead_data['status_id'] = config.AMOCRM_STATUS_ID

            logger.info(f"Creating lead with data: {json.dumps(lead_data, indent=2)}")
            response = self._make_request('POST', 'leads', json=[lead_data])
            logger.info(f"Create lead response: {response.text}")
            response.raise_for_status()

            result = response.json()
            return result['_embedded']['leads'][0]['id']

        except Exception as e:
            logger.error(f"Error creating lead: {e}")
            return None

    def update_lead(self, lead_id: int, data: Dict) -> bool:
        """Update lead in amoCRM"""
        try:
            custom_fields = []

            # Tour details
            if 'tour_campus' in data:
                custom_fields.append({
                    'field_name': 'Tour Campus',
                    'values': [{'value': data['tour_campus']}]
                })

            if 'tour_date' in data:
                custom_fields.append({
                    'field_name': 'Tour Date',
                    'values': [{'value': data['tour_date']}]
                })

            if 'tour_time' in data:
                custom_fields.append({
                    'field_name': 'Tour Time',
                    'values': [{'value': data['tour_time']}]
                })

            if 'tour_status' in data:
                custom_fields.append({
                    'field_name': 'Tour Status',
                    'values': [{'value': data['tour_status']}]
                })

            lead_data = {
                'custom_fields_values': custom_fields
            }

            response = self._make_request('PATCH', f'leads/{lead_id}', json=lead_data)
            response.raise_for_status()

            return True

        except Exception as e:
            logger.error(f"Error updating lead: {e}")
            return False

    def create_task(self, lead_id: int, text: str, complete_till: int = None) -> bool:
        """Create a task in amoCRM"""
        try:
            if not complete_till:
                # Default: complete within 1 hour
                complete_till = int(time.time()) + 3600

            task_data = {
                'text': text,
                'complete_till': complete_till,
                'entity_id': lead_id,
                'entity_type': 'leads'
            }

            response = self._make_request('POST', 'tasks', json=[task_data])
            response.raise_for_status()

            return True

        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return False

    def add_note(self, lead_id: int, note_text: str) -> bool:
        """Add a note to a lead"""
        try:
            note_data = {
                'note_type': 'common',
                'params': {
                    'text': note_text
                },
                'entity_id': lead_id
            }

            response = self._make_request('POST', f'leads/{lead_id}/notes', json=[note_data])
            response.raise_for_status()

            return True

        except Exception as e:
            logger.error(f"Error adding note: {e}")
            return False

    def send_message_to_chat(self, chat_id: str, text: str, sender_name: str) -> bool:
        """
        Send message to amoCRM Chat (via Chat API)
        
        Note: Standard 'amojo' API is complex and requires separate account_id.
        For External Integrations, we use:
        POST /v1/chats/{chat_id}/messages
        """
        try:
            # We need a unique chat_id for the conversation. 
            # In amoCRM context, the 'conversation_id' is usually tied to the visitor/contact.
            # For simplicity, we use the Telegram User ID as the conversation ID.
            
            # Since we are using a "Custom Integration" approach without full amojo registration,
            # we might not have access to the full Chat API unless we set up the "Online Chat" channel properly in UI.
            
            # However, let's try the standard endpoint if we have the channel ID (Scope ID).
            scope_id = self.client_id  # Using Client ID as scope
            
            # API Endpoint for sending messages to a chat session
            # Note: This often requires the amojo_id which we found earlier.
            # But standard docs say: https://amojo.amocrm.ru/v2/origin/custom/{scope_id}/chats/{chat_id}/messages
            
            url = f"https://amojo.amocrm.ru/v2/origin/custom/{scope_id}/chats/{chat_id}/messages"
            
            # We need to sign the request.
            # For simplicity in this iteration, we will send raw requests and log the result.
            # A proper signature requires: MD5(body + secret)
            
            import hashlib
            
            message_data = {
                "event_type": "new_message",
                "payload": {
                    "timestamp": int(time.time()),
                    "m_id": str(time.time()), # Unique message ID
                    "msg": text,
                    "sender": {
                        "id": chat_id, # User ID from Telegram
                        "name": sender_name,
                        "ref_id": chat_id
                    }
                }
            }
            
            body = json.dumps(message_data)
            
            # Check-Sum: X-Signature
            # MD5(body + secret_key)
            checksum = hashlib.md5((body + self.client_secret).encode('utf-8')).hexdigest()
            
            headers = {
                'Content-Type': 'application/json',
                'X-Signature': checksum.lower()
            }
            
            response = requests.post(url, data=body, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Error sending chat message: {response.status_code} - {response.text}")
                return False
                
            return True

        except Exception as e:
            logger.error(f"Error sending message to chat: {e}")
            return False

    def verify_webhook_signature(self, signature: str, body: bytes) -> bool:
        """Verify X-Signature from amoCRM webhook"""
        try:
            import hashlib
            # Signature is MD5(body + secret) usually, but for some hooks it might differ.
            # For Chat API webhooks, it is often MD5(body + client_secret).
            
            calculated = hashlib.md5(body + self.client_secret.encode('utf-8')).hexdigest()
            return calculated.lower() == signature.lower()
        except Exception:
            return False

    def get_lead_by_id(self, lead_id: int) -> Optional[Dict]:
        """Get lead details by ID, including contacts"""
        try:
            response = self._make_request('GET', f'leads/{lead_id}', params={'with': 'contacts'})
            if response.status_code == 204:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting lead {lead_id}: {e}")
            return None

    def get_contact_by_id(self, contact_id: int) -> Optional[Dict]:
        """Get contact details by ID"""
        try:
            response = self._make_request('GET', f'contacts/{contact_id}')
            if response.status_code == 204:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting contact {contact_id}: {e}")
            return None
