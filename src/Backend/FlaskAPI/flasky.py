from flask import Flask, request, jsonify, Response
import re
import logging
from datetime import datetime
import time
import random
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from decouple import config

from Backend.database.data import db, init_database, save_conversation, get_conversation_history
from Backend.Model.loadModel import initialize_model, get_ai_response
from Backend.Model.response_handler import clean_response, add_conversational_elements
from Backend.Model.conversation_state import ConversationState, get_conversation_state, update_conversation_state
from twilioM.nurseTalk import send_message as external_send_message

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
    """Clean up the AI response with clear diagnosis and first aid steps"""
    # Remove [augmented] tags and clean initial text
    text = re.sub(r'\[augmented\]', '', text)
    
    # Extract diagnosis more accurately
    diagnosis_match = re.search(r'(?:Assessment:|Diagnosis:)\s*([^.!?\n]+)', text, re.IGNORECASE)
    diagnosis = ""
    if diagnosis_match:
        diagnosis = diagnosis_match.group(1).strip()
        # Clean up diagnosis
        diagnosis = re.sub(r'(?:Assessment:|Diagnosis:)', '', diagnosis)
        diagnosis = re.sub(r'ptoms:|symptoms:', '', diagnosis, flags=re.IGNORECASE)
    
    # Extract first aid steps
    first_aid_steps = []
    emergency_step = None
    if 'First Aid:' in text:
        first_aid_sections = text.split('First Aid:')[1:]
        seen_steps = set()
        
        for section in first_aid_sections:
            steps = [s.strip() for s in re.split(r'[.;]\s*', section) if s.strip()]
            
            for step in steps:
                step_lower = step.lower()
                # Identify emergency steps
                if any(term in step_lower for term in ['emergency', 'urgent', 'call emergency', 'immediate']):
                    emergency_step = "Seek immediate medical attention"
                    continue
                
                # Filter out garbage and duplicates
                if (not any(x in step_lower for x in ['ptoms:', 'symptoms:', 'netmessage', 'first aid:', 'assessment:']) and
                    step_lower not in seen_steps and
                    len(step) > 3):
                    
                    # Clean up the step
                    clean_step = step.strip('., ')
                    if clean_step and clean_step.lower() not in seen_steps:
                        first_aid_steps.append(f"• {clean_step}")
                        seen_steps.add(clean_step.lower())
    
    # Build the response with proper formatting
    cleaned_text = "*Diagnosis*:\n"
    cleaned_text += diagnosis if diagnosis else "Pending medical assessment"
    
    if first_aid_steps:
        cleaned_text += "\n\n*First Aid Steps*:\n"
        cleaned_text += "\n".join(first_aid_steps)
        # Add emergency step at the end if present
        if emergency_step:
            cleaned_text += f"\n• {emergency_step}"
    
    # Add emergency warning only if emergency step present
    if emergency_step:
        cleaned_text += "\n\n⚠️ *URGENT*: Immediate medical attention required!"
    
    return cleaned_text

def add_conversational_elements(response):
    """Add a single follow-up question after the medical advice"""
    follow_ups = [
        "\n\nHow long has your child been experiencing these symptoms?",
        "\n\nHas your child been feeding normally?",
        "\n\nWhat temperature readings have you observed?",
        "\n\nHave you tried any remedies so far?"
    ]
    return f"{response}{random.choice(follow_ups)}"

@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    logger.info(f"Incoming request: {request.form}")
    start_time = time.time()
    
    try:
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        user_input = request.form.get('Body', '').strip()
        
        if not from_number or not user_input:
            logger.warning("Missing From/Body in request")
            return _generate_twiml_response("Missing required fields")
        
        # Get current conversation state and handle greeting
        current_state = get_conversation_state(from_number)
        if current_state == ConversationState.GREETING:
            if any(greeting in user_input.lower() for greeting in ['hi', 'hello', 'hey']):
                update_conversation_state(from_number, ConversationState.COLLECTING_INFO)
                return _generate_twiml_response("Hello! I'm your virtual health assistant. How can I help you today?")
        
        # Get AI response with context
        conversation_history = get_conversation_history(from_number, limit=5)
        try:
            bot_response, response_time = get_ai_response(user_input, conversation_history)
        except Exception as ai_error:
            logger.error(f"AI model error: {str(ai_error)}")
            bot_response = "I'm having technical difficulties. A nurse will contact you shortly."
            response_time = 0

        # Validate and clean response
        if not bot_response or len(bot_response.strip()) == 0:
            logger.error("Empty response generated from AI model")
            bot_response = "I apologize, but I couldn't generate a proper response. A nurse will be notified."
            response_time = 0
        else:
            bot_response = clean_response(bot_response)
            bot_response = add_conversational_elements(bot_response)
            
        # Update conversation state
        if "goodbye" in user_input.lower() or "thank" in user_input.lower():
            update_conversation_state(from_number, ConversationState.FAREWELL)
            bot_response += "\n\nTake care! Feel free to reach out if you need anything else."
        else:
            update_conversation_state(from_number, ConversationState.PROVIDING_ADVICE)

        # Save initial conversation state
        save_conversation(
            phone_number=from_number,
            user_input=user_input,
            bot_response=bot_response,
            response_time=response_time,
            status='processing'
        )
        
        # Send message
        logger.info(f"Attempting to send message to {from_number}: {bot_response[:100]}...")
        send_result = external_send_message(
            to_number=f"whatsapp:{from_number}" if not from_number.startswith('whatsapp:') else from_number,
            body_text=bot_response,
            message_type='whatsapp'
        )

        # Handle send result
        if not send_result.get('success'):
            logger.error(f"Failed to send message: {send_result.get('error')}")
            return _generate_twiml_response("Failed to send message. Please try again.")

        # Update final conversation status
        save_conversation(
            phone_number=from_number,
            user_input=user_input,
            bot_response=bot_response,
            response_time=response_time,
            status='sent'
        )

        logger.info(f"Message sent successfully to {from_number}")
        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
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