import logging
import re
from time import sleep
from decouple import config
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

class TwilioClient:
    def __init__(self):
        self.client = None
        self.twilio_number = None
        self._initialize_client()
        self.retry_count = 2  # Number of send retries

    def _initialize_client(self):
        try:
            account_sid = config("TWILIO_ACCOUNT_SID")
            auth_token = config("TWILIO_AUTH_TOKEN")
            self.twilio_number = config('TWILIO_NUMBER')
            
            if not all([account_sid, auth_token, self.twilio_number]):
                raise ValueError("Missing Twilio credentials in environment variables")
            
            self.client = Client(account_sid, auth_token)
            logger.info("Twilio client initialized successfully")
            
        except Exception as e:
            logger.exception("Failed to initialize Twilio client")
            raise RuntimeError(f"Twilio init failed: {str(e)}")

    def _validate_phone_number(self, number):
        """Validate and format E.164 numbers"""
        cleaned = re.sub(r"[^0-9+]", "", number)
        if not cleaned.startswith("+"):
            cleaned = f"+{cleaned}"
        return cleaned

    def send_whatsapp_message(self, to_number, body_text):
        """Send WhatsApp message with segmentation and retries"""
        try:
            # Validate and clean number
            to_number = self._validate_phone_number(to_number)
            
            # Segment long messages
            messages = self._segment_message(body_text)
            results = []
            
            for segment in messages:
                for attempt in range(self.retry_count + 1):
                    try:
                        message = self.client.messages.create(
                            from_=f'whatsapp:{self.twilio_number}',
                            body=segment,
                            to=f'whatsapp:{to_number}'
                        )
                        results.append({
                            'success': True,
                            'message_sid': message.sid,
                            'segment': segment[:30] + "..." if len(segment) > 30 else segment
                        })
                        break  # Exit retry loop on success
                    except TwilioRestException as e:
                        if attempt < self.retry_count:
                            wait = 2 ** attempt  # Exponential backoff
                            logger.warning(f"Retry {attempt+1}/{self.retry_count} in {wait}s for {to_number}")
                            sleep(wait)
                        else:
                            raise
                
            logger.info(f'Sent {len(messages)} segments to {to_number}')
            return {
                'success': True,
                'segments': results
            }
        except TwilioRestException as e:
            logger.error(f'Twilio error ({e.code}): {e.msg}')
            return {
                'success': False,
                'error': f"Twilio error {e.code}: {e.msg}",
                'retries_exhausted': True
            }
        except Exception as e:
            logger.exception(f'Unexpected error sending to {to_number}')
            return {
                'success': False,
                'error': str(e)
            }

    def _segment_message(self, text, max_length=1600):
        """Split long messages into segments"""
        if len(text) <= max_length:
            return [text]
        
        segments = []
        while text:
            # Find last natural break point within limit
            segment = text[:max_length]
            break_points = [segment.rfind("."), segment.rfind("?"), segment.rfind("!"), segment.rfind("\n")]
            last_break = max(p for p in break_points if p != -1) if any(p != -1 for p in break_points) else max_length - 1
            
            segments.append(text[:last_break + 1].strip())
            text = text[last_break + 1:].strip()
            
            # Add continuation marker
            if text:
                segments[-1] += ".."
                text = "(cont.) " + text
        
        return segments

# Global instance
twilio_client = TwilioClient()

def send_message(to_number, body_text, message_type='whatsapp'):
    if message_type.lower() == 'whatsapp':
        return twilio_client.send_whatsapp_message(to_number, body_text)
    else:
        raise ValueError(f"Unsupported message type: {message_type}")