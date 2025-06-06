from flask import Flask, request, jsonify, Response
import re
import logging
from datetime import datetime
import time
from twilio.request_validator import RequestValidator  # Add this
from twilio.twiml.messaging_response import MessagingResponse  # Add this
from decouple import config  # Add this if not already imported

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
app.config['TWILIO_AUTH_TOKEN'] = config('TWILIO_AUTH_TOKEN')  # Load from .env

# Initialize components
init_database(app)
initialize_model()

def clean_response(text):
    """Clean up the AI response by removing repetitive elements and tags"""
    # Remove [augmented] tags
    text = re.sub(r'\[augmented\]', '', text)
    
    # Split on the first occurrence of "First Aid:"
    parts = text.split('First Aid:', 1)
    
    # Clean diagnosis part (everything before first "First Aid:")
    diagnosis = parts[0].strip()
    if not diagnosis:
        diagnosis = "Assessment unclear"
    
    # Clean First Aid part if it exists
    first_aid = ""
    if len(parts) > 1:
        first_aid = parts[1].strip()
        # Remove subsequent duplicate First Aid sections
        first_aid = re.sub(r'(?:First Aid:)?\s*(.*?)(?=First Aid:|$)', r'\1', first_aid)
        # Remove duplicate instructions within First Aid section
        first_aid = '. '.join(dict.fromkeys(
            [x.strip() for x in first_aid.split('.') if x.strip()]
        ))
    
    # Combine sections with proper formatting
    cleaned_text = f"Assessment: {diagnosis}"
    if first_aid:
        cleaned_text += f"\nFirst Aid: {first_aid}"
    
    # Remove repetitive phrases
    cleaned_text = re.sub(r'([^.]+)(\. \1)+', r'\1', cleaned_text)
    
    # Remove repetitive "5 min" entries
    cleaned_text = re.sub(r'(5 min\.?\s*)+', '5 min. ', cleaned_text)
    
    # Clean up whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    # Add emergency note if needed
    if any(word in cleaned_text.lower() for word in ['urgent', 'emergency', 'immediate']):
        cleaned_text += "\nNote: For severe symptoms, immediate medical attention is crucial."
    
    return cleaned_text

@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    logger.info(f"Incoming request: {request.form}")
    start_time = time.time()
    
    try:
        # Extract form data
        from_number = request.form.get('From', '').replace('whatsapp:', '')  # Clean number
        user_input = request.form.get('Body', '').strip()
        
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
            if not bot_response or len(bot_response.strip()) == 0:
                logger.error("Empty response generated from AI model")
                bot_response = "I apologize, but I couldn't generate a proper response. A nurse will be notified."
                response_time = 0
                
            # Clean the response before sending
            bot_response = clean_response(bot_response)
            
            # Validate cleaned response
            if not bot_response or len(bot_response.strip()) == 0:
                logger.error("Empty response after cleaning")
                return _generate_twiml_response("Internal error occurred. Please try again later.")
                
        except Exception as ai_error:
            logger.error(f"AI model error: {str(ai_error)}")
            bot_response = "I'm having technical difficulties. A nurse will contact you shortly."
            response_time = 0
        
        # Validate response before sending
        if not bot_response or len(bot_response.strip()) == 0:
            logger.error("Attempting to send empty message")
            return _generate_twiml_response("Internal error occurred. Please try again later.")

        # 5. Save conversation BEFORE sending
        save_conversation(
            phone_number=from_number,
            user_input=user_input,
            bot_response=bot_response,
            response_time=response_time,
            status='processing'
        )
        
        # Add logging before send attempt
        logger.info(f"Attempting to send message to {from_number}: {bot_response[:100]}...")
        
        # Actively send the WhatsApp message
        logger.debug(f"Sending message - To: {from_number}, Body length: {len(bot_response)}")
        send_result = external_send_message(
            to_number=f"whatsapp:{from_number}" if not from_number.startswith('whatsapp:') else from_number,
            body_text=bot_response,
            message_type='whatsapp'
        )

        if not send_result.get('success'):
            logger.error(f"Failed to send message: {send_result.get('error')}")
            return _generate_twiml_response("Failed to send message. Please try again.")

        # Update conversation status
        save_conversation(
            phone_number=from_number,
            user_input=user_input,
            bot_response=bot_response,
            response_time=response_time,
            status='sent' if send_result.get('success') else 'failed'
        )

        # Log success
        logger.info(f"Message sent successfully to {from_number}")
        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        # Try to send error message to user
        try:
            external_send_message(
                to_number=from_number,
                body_text="Sorry, there was an error processing your message. Please try again later.",
                message_type='whatsapp'
            )
        except:
            logger.error("Failed to send error message")
        return Response("Error", status=500)

def _generate_twiml_response(message):
    """Helper to generate TwiML responses"""
    resp = MessagingResponse()
    resp.message(message)
    return Response(str(resp), content_type='application/xml')

# ... keep your existing /health and /conversations endpoints unchanged ...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)