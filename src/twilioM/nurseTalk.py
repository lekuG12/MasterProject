import logging
import os

from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from decouple import config


logger = logging.getLogger(__name__)


class TwilioClient:
    def __init__(self):
        self.client = None
        self.twilio_number = None
        self._initialize_client()

   
    def _initialize_client(self):
        """Initialize Twilio client with credentials"""
        try:
            account_sid = config("TWILIO_ACCOUNT_SID")
            auth_token = config("TWILIO_AUTH_TOKEN")
            self.twilio_number = config('TWILIO_NUMBER')
            
            if not all([account_sid, auth_token, self.twilio_number]):
                raise ValueError("Missing Twilio credentials in environment variables")
            
            self.client = Client(account_sid, auth_token)
            logger.info("Twilio client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {str(e)}")
            raise

    
    def send_whatsapp_message(self, to_number, body_text):
        """Send WhatsApp message via Twilio"""
        try:
            # Send message
            message = self.client.messages.create(
                from_=f'whatsapp:{self.twilio_number}',
                body=body_text,
                to=f'whatsapp:{to_number}'
            )
            
            logger.info(f'WhatsApp message sent to {to_number}: {message.sid}')
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'to': to_number
            }
        except TwilioException as e:
            logger.error(f'Twilio error sending message to {to_number}: {str(e)}')
            raise Exception(f'Twilio error: {str(e)}')
        except Exception as e:
            logger.error(f'Error sending message to {to_number}: {str(e)}')
            raise Exception(f'Message sending failed: {str(e)}')


twilio_client = TwilioClient()

def send_message(to_number, body_text, message_type='whatsapp'):
    """Send message - main interface function"""
    if message_type.lower() == 'whatsapp':
        return twilio_client.send_whatsapp_message(to_number, body_text)