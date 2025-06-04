from flask import Flask, request, jsonify, Response
import re
import logging
from datetime import datetime
import time
from twilio.request_validator import RequestValidator  # Add this
from twilio.twiml.messaging_response import MessagingResponse  # Add this

from Backend.database.data import db, init_database, save_conversation, get_conversation_history
from Backend.Model.loadModel import initialize_model, get_ai_response
from twilioM.nurseTalk import send_message as external_send_message  # Rename import

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nurse_talk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TWILIO_AUTH_TOKEN'] = 'YOUR_TWILIO_AUTH_TOKEN'  # Set in environment later

# Initialize components
init_database(app)
initialize_model()

@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():  # Renamed function
    start_time = time.time()
    
    # 1. Validate Twilio signature
    # validator = RequestValidator(app.config['TWILIO_AUTH_TOKEN'])
    # signature = request.headers.get('X-Twilio-Signature', '')
    # if not validator.validate(request.url, request.form, signature):
    #     logger.warning("Invalid Twilio signature")
    #     return Response("Unauthorized", status=403)
    
    try:
        # 2. Extract form data (Twilio format)
        from_number = request.form.get('From', '')
        user_input = request.form.get('Body', '').strip()
        to_number = request.form.get('To', '')  # Your Twilio number
        
        if not from_number or not user_input:
            logger.warning("Missing From/Body in request")
            return _generate_twiml_response("Missing required fields")
        
        if len(user_input) > 1600:
            return _generate_twiml_response("Message too long (max 1600 characters)")
        
        # 3. Get context
        conversation_history = get_conversation_history(from_number, limit=5)
        
        # 4. Generate AI response
        try:
            bot_response, response_time = get_ai_response(user_input, conversation_history)
        except Exception as ai_error:
            logger.error(f"AI model error: {str(ai_error)}")
            bot_response = "I'm having technical difficulties. A nurse will contact you shortly."
            response_time = 0
        
        # 5. Save conversation BEFORE sending
        save_conversation(
            phone_number=from_number,
            user_input=user_input,
            bot_response=bot_response,
            response_time=response_time,
            status='processing'
        )
        
        # 6. Return TwiML response
        resp = MessagingResponse()
        resp.message(bot_response)
        twiml = str(resp)
        
        # 7. Update status after successful response generation
        save_conversation(
            phone_number=from_number,
            user_input=user_input,
            bot_response=bot_response,
            response_time=response_time,
            status='sent'
        )
        
        total_time = time.time() - start_time
        logger.info(f"Processed WhatsApp message in {total_time:.2f}s")
        
        return Response(twiml, content_type='application/xml')
    
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return _generate_twiml_response("An error occurred. Please try again later.")

def _generate_twiml_response(message):
    """Helper to generate TwiML responses"""
    resp = MessagingResponse()
    resp.message(message)
    return Response(str(resp), content_type='application/xml')

# ... keep your existing /health and /conversations endpoints unchanged ...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)