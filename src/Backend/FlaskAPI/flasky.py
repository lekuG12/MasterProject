from flask import Flask, request, jsonify, Response, send_file
import re
import logging
from datetime import datetime
import os
import time
import random
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from decouple import config

from Backend.database.data import db, init_database, save_conversation, get_conversation_history
from Backend.Model.loadModel import initialize_model, get_ai_response
from Backend.Model.response_handler import clean_response, add_conversational_elements
from Backend.Model.conversation_state import ConversationState, get_conversation_state, update_conversation_state
from twilioM.nurseTalk import send_message as external_send_message
from AIV.translateTranscribe import TTSService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nurse_talk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TWILIO_AUTH_TOKEN'] = config('TWILIO_AUTH_TOKEN')
app.config['TWILIO_ACCOUNT_SID'] = config('TWILIO_ACCOUNT_SID')  # Add this
app.config['STATIC_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app.config['TEMP_FOLDER'] = os.path.join(app.config['STATIC_FOLDER'], 'temp')

# Initialize Twilio client for direct audio sending
twilio_client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])

# Initialize components
init_database(app)
initialize_model()

# Initialize TTS service
tts_service = TTSService()

# Ensure temp folder exists
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

def clean_response(text):
    """Clean up the AI response with clear diagnosis and first aid steps"""
    # Remove [augmented] tags and clean initial text
    text = re.sub(r'\[augmented\]', '', text)
    
    # Extract
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

def send_whatsapp_audio(to_number, audio_url):
    """Send audio message directly using Twilio client"""
    try:
        message = twilio_client.messages.create(
            from_='whatsapp:+14155238886',  # Your Twilio WhatsApp number
            to=to_number,
            media_url=[audio_url],
            body=""  # Empty body for audio-only message
        )
        logger.info(f"Audio message sent successfully: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send audio message: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages"""
    logger.info("Received webhook request")
    try:
        # Get and format the phone number
        from_number = request.form.get('From', '')
        if not from_number:
            return generate_twiml_response("Missing sender number")
            
        # Ensure proper WhatsApp format
        if not from_number.startswith('whatsapp:'):
            from_number = f"whatsapp:+{from_number.lstrip('+')}"
        
        # Check if this is a text or audio message
        num_media = int(request.form.get('NumMedia', 0))
        user_input = None

        if num_media > 0 and request.form.get('MediaContentType0', '').startswith('audio/'):
            # Handle audio input
            media_url = request.form.get('MediaUrl0')
            audio_extension = request.form.get('MediaContentType0').split('/')[-1]
            temp_audio_path = os.path.join(app.config['STATIC_FOLDER'], 'temp', 
                                         f"input_{int(time.time())}.{audio_extension}")
            
            os.makedirs(os.path.dirname(temp_audio_path), exist_ok=True)
            
            # Download and transcribe audio
            if tts_service.download_audio_from_url(media_url, temp_audio_path):
                user_input = tts_service.transcribe_audio(temp_audio_path)
                # Clean up temporary file
                os.remove(temp_audio_path)
        else:
            # Handle text input
            user_input = request.form.get('Body', '').strip()

        if not user_input:
            return generate_twiml_response("Could not process your message. Please try again.")

        logger.info(f"Processing message from {from_number}: {user_input}")

        # Get AI response
        bot_response, response_time = get_ai_response(user_input, get_conversation_history(from_number))
        cleaned_response = clean_response(bot_response)
        final_response = add_conversational_elements(cleaned_response)

        # Generate audio before sending response
        audio_filename = tts_service.generate_speech(final_response, from_number)
        
        if audio_filename:
            # Construct the public URL for the audio file
            audio_url = f"https://3eac-129-0-79-131.ngrok-free.app/audio/{audio_filename}"
            
            # First send the text message
            text_result = external_send_message(
                to_number=from_number,
                body_text=final_response,
                message_type='whatsapp'
            )
            
            # Then send the audio message separately
            audio_result = twilio_client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_number,
                media_url=[audio_url]
            )
            
            status = 'sent_with_audio' if audio_result.sid else 'failed'
        else:
            # Fallback to text-only
            send_result = external_send_message(
                to_number=from_number,
                body_text=final_response,
                message_type='whatsapp'
            )
            status = 'sent_text_only'

        # Save conversation
        save_conversation(
            phone_number=from_number,
            user_input=user_input,
            bot_response=final_response,
            response_time=response_time,
            status=status
        )

        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return generate_twiml_response("Sorry, there was an error processing your request.")

def generate_twiml_response(message):
    """Generate TwiML response for WhatsApp"""
    resp = MessagingResponse()
    resp.message(message)
    return str(resp)

@app.route('/audio/<filename>')
def serve_audio(filename):
    try:
        safe_filename = os.path.basename(filename)
        audio_path = os.path.join(app.config['STATIC_FOLDER'], 'audio', safe_filename)
        
        if os.path.exists(audio_path):
            return send_file(
                audio_path,
                mimetype='audio/mpeg',  # Changed from audio/mp3 to audio/mpeg
                as_attachment=False,     # Changed to False to allow direct playback
                download_name=safe_filename
            )
        else:
            logger.error(f"Audio file not found: {audio_path}")
            return Response("Audio file not found", status=404)
    except Exception as e:
        logger.error(f"Error serving audio: {e}")
        return Response("Error serving audio", status=500)

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/conversations/<phone_number>')
def get_conversations(phone_number):
    """Get conversation history for a phone number"""
    try:
        # Ensure proper WhatsApp format for lookup
        if not phone_number.startswith('whatsapp:'):
            phone_number = f"whatsapp:+{phone_number.lstrip('+')}"
        
        history = get_conversation_history(phone_number)
        return jsonify({
            "phone_number": phone_number,
            "conversations": history
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)