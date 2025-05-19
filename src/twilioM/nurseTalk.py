import logging

from twilio.rest import Client
from decouple import config

account_sid = config("TWILIO_ACCOUNT_SID")
auth_token = config("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)
twilio_number = config('TWILIO_NUMBER')


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sendMessage(to_number, body_text):
    try:
        message = Client.messages.create(
            from_='WhatsAPP: {}'.format(twilio_number),
            body=body_text,
            to='WhatsAPP: {}'.format(to_number)
        )

        logger.info('Message sent to {}: {}'.format(to_number, message.body))

    except Exception as e:
        logger.error('Error sending message to {}: {}'.format(to_number, e))