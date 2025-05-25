import logging
import os

from twilio.rest import Client
from decouple import config


twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

twilio_whatsapp = os.getenv('TWILIO_NUMBER')

account_sid = config("TWILIO_ACCOUNT_SID")
auth_token = config("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)
twilio_number = config('TWILIO_NUMBER')


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sendMessage(to_number, body_text):
    try:
        message = client.messages.create(
            from_=f'whatsapp:{twilio_number}',
            body=body_text,
            to=f'whatsapp:{to_number}'
        )
        logger.info(f'Message sent to {to_number}: {message.body}')
        return message
    except Exception as e:
        logger.error(f'Error sending message to {to_number}: {str(e)}')
        raise e