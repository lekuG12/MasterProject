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
from Backend.Model.loadModel import initialize_model, clear_model_cache, get_ai_response
from Backend.Model.response_handler import clean_response, add_conversational_elements
from Backend.Model.conversation_state import ConversationState, get_conversation_state, update_conversation_state
from twilioM.nurseTalk import send_message as external_send_message
from AIV.translateTranscribe import TTSService
from Backend.Model.conversation_patterns import ConversationManager
from Backend.Model.model_singleton import ModelSingleton

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

# Add after existing app.config settings
app.config.update(
    MAX_AUDIO_SIZE=16 * 1024 * 1024,  # 16MB max size
    ALLOWED_AUDIO_TYPES=['audio/ogg', 'audio/mpeg', 'audio/mp3', 'audio/wav'],
    AUDIO_CONVERSION_ENABLED=True
)
app.config['BASE_URL'] = config('BASE_URL', default='http://localhost:5000')

# Initialize Twilio client for direct audio sending
twilio_client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])

# Initialize components with better error handling
try:
    init_database(app)
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    raise RuntimeError("Failed to initialize database")

# Initialize AI model
try:
    model_singleton = ModelSingleton.get_instance()
    model = model_singleton.get_model()
    logger.info("AI model reference obtained successfully")
except Exception as e:
    logger.error(f"Model initialization failed: {e}")
    raise RuntimeError(f"Failed to initialize AI model: {str(e)}")

# Initialize other components
tts_service = TTSService()
conversation_manager = ConversationManager()

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
    """Add contextual follow-up questions and return both response and selected question"""
    follow_ups = {
        'fever': [
            "What is the current temperature?",
            "How long has the fever lasted?",
            "Have you taken any fever medication?",
            "Is there any shivering or sweating?",
            "What time of day does the fever peak?"
        ],
        'pain': [
            "On a scale of 1-10, how severe is the pain?",
            "Is the pain constant or does it come and go?",
            "What makes the pain better or worse?",
            "Can you point to where it hurts the most?",
            "Does the pain move to other areas?"
        ],
        'general': [
            "How long have these symptoms been present?",
            "Has your child been feeding normally?",
            "Have you tried any remedies so far?",
            "Are there any other symptoms I should know about?",
            "Has your child had similar symptoms before?",
            "Has there been any recent exposure to sick people?",
            "How is your child's energy level?",
            "Are there any changes in sleep patterns?"
        ]
    }
    
    # Get conversation state for this user
    conversation_state = get_conversation_state(request.form.get('From', ''))
    
    # Track previously asked questions
    if not hasattr(conversation_state, 'asked_questions'):
        conversation_state.asked_questions = set()
    
    # Determine which question set to use based on response content
    if 'fever' in response.lower():
        available_questions = follow_ups['fever']
    elif 'pain' in response.lower():
        available_questions = follow_ups['pain']
    else:
        available_questions = follow_ups['general']
    
    # Filter out previously asked questions
    unasked_questions = [q for q in available_questions if q not in conversation_state.asked_questions]
    
    # If all questions have been asked, reset the history
    if not unasked_questions:
        conversation_state.asked_questions.clear()
        unasked_questions = available_questions
    
    # Select a random question from unasked ones
    selected_question = random.choice(unasked_questions)
    
    # Add to asked questions history
    conversation_state.asked_questions.add(selected_question)
    
    # Update conversation state
    update_conversation_state(request.form.get('From', ''), conversation_state)
    
    final_response = f"{response}\n\n{selected_question}"
    return final_response, selected_question

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

def generate_twiml_response(message, status="info"):
    """Generate TwiML response with appropriate emoji and styling"""
    emoji_map = {
        "info": "ℹ️",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "processing": "⏳",
        "listening": "👂",
        "thinking": "🤔",
        "speaking": "🗣️"
    }
    emoji = emoji_map.get(status, "")
    response = MessagingResponse()
    response.message(f"{emoji} {message}")
    return str(response)

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

        # Initial acknowledgment based on input type
        if int(request.form.get('NumMedia', 0)) > 0:
            external_send_message(
                to_number=from_number,
                body_text="👂 Processing your voice message...",
                message_type='whatsapp'
            )
        else:
            external_send_message(
                to_number=from_number,
                body_text="✅ Processing...",
                message_type='whatsapp'
            )

        # Check for quick responses first
        if not num_media:  # Only for text messages
            quick_response = conversation_manager.get_quick_response(
                request.form.get('Body', '').strip(),
                from_number
            )
            if quick_response:
                external_send_message(
                    to_number=from_number,
                    body_text=quick_response,
                    message_type='whatsapp'
                )
                save_conversation(
                    phone_number=from_number,
                    user_input=request.form.get('Body', '').strip(),
                    bot_response=quick_response,
                    status='quick_response'
                )
                return Response("OK", status=200)

        # Process either audio or text input
        if num_media > 0 and request.form.get('MediaContentType0', '').startswith('audio/'):
            # Handle audio input
            try:
                media_url = request.form.get('MediaUrl0')
                content_type = request.form.get('MediaContentType0')
                
                if not media_url:
                    logger.error("No media URL provided")
                    return generate_twiml_response("Audio message received but no media URL found")
                    
                if content_type not in app.config['ALLOWED_AUDIO_TYPES']:
                    logger.error(f"Unsupported audio type: {content_type}")
                    return generate_twiml_response("Sorry, this audio format is not supported")
                
                # Generate unique filename with timestamp
                audio_extension = content_type.split('/')[-1]
                timestamp = int(time.time())
                temp_audio_path = os.path.join(
                    app.config['TEMP_FOLDER'],
                    f"input_{timestamp}_{random.randint(1000, 9999)}.{audio_extension}"
                )
                
                logger.info(f"Downloading audio from {media_url} to {temp_audio_path}")
                
                # Ensure temp directory exists
                os.makedirs(os.path.dirname(temp_audio_path), exist_ok=True)
                
                # Download and process audio
                if not tts_service.download_audio_from_url(media_url, temp_audio_path):
                    logger.error("Failed to download audio file")
                    return generate_twiml_response("Sorry, couldn't download your audio message")
                
                # Verify file was downloaded and has content
                if not os.path.exists(temp_audio_path) or os.path.getsize(temp_audio_path) == 0:
                    logger.error("Downloaded audio file is empty or missing")
                    return generate_twiml_response("Sorry, there was an issue with your audio message")
                    
                logger.info("Transcribing audio file")
                user_input = tts_service.transcribe_audio(temp_audio_path)
                
                if not user_input:
                    logger.error("Audio transcription failed")
                    return generate_twiml_response("Sorry, I couldn't understand the audio. Please try again")
                    
                logger.info(f"Successfully transcribed audio to: {user_input}")
                
            except Exception as e:
                logger.error(f"Error processing audio: {str(e)}", exc_info=True)
                return generate_twiml_response("Sorry, there was an error processing your audio message")
            
            finally:
                # Clean up temporary file
                if os.path.exists(temp_audio_path):
                    try:
                        os.remove(temp_audio_path)
                        logger.info(f"Cleaned up temporary file: {temp_audio_path}")
                    except Exception as e:
                        logger.error(f"Error cleaning up temp file: {str(e)}")
        else:
            # Handle text input
            user_input = request.form.get('Body', '').strip()

        if not user_input:
            return generate_twiml_response("Could not process your message. Please try again.")

        logger.info(f"Processing message from {from_number}: {user_input}")

        # Get context history before processing
        context_history = conversation_manager.get_context_history(from_number)

        # Get and process AI response with context
        try:
            bot_response, response_time = get_ai_response(
                user_input, 
                get_conversation_history(from_number),
                context_history
            )
        except RuntimeError as e:
            logger.error(f"AI model error: {e}")
            return generate_twiml_response(
                "Sorry, the AI service is currently unavailable. Please try again later.",
                status="error"
            )

        cleaned_response = clean_response(bot_response)
        final_response, follow_up_question = add_conversational_elements(cleaned_response)

        # Always generate audio response
        external_send_message(
            to_number=from_number,
            body_text="🎯 Creating your response...",
            message_type='whatsapp'
        )

        audio_filename = tts_service.generate_speech(final_response, from_number)
        
        # Send both text and audio responses
        if audio_filename:
            # Send text response first
            text_result = external_send_message(
                to_number=from_number,
                body_text=final_response,
                message_type='whatsapp'
            )
            
            # Construct audio URL using configured base URL
            audio_url = f"{app.config['BASE_URL']}/audio/{audio_filename}"
            logger.info(f"Attempting to send audio with URL: {audio_url}")

            # Verify audio file exists before sending
            audio_path = os.path.join(app.config['STATIC_FOLDER'], 'audio', audio_filename)
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found at {audio_path}")
                raise FileNotFoundError("Audio file not found")

            # Send audio message
            audio_result = twilio_client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_number,
                media_url=[audio_url]
            )
            
            logger.info(f"Audio message sent successfully. SID: {audio_result.sid}")
            status = 'sent_with_audio' if audio_result.sid else 'failed'
        else:
            # Fallback to text-only if audio generation fails
            text_result = external_send_message(
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

        # Update session with new context and follow-up
        conversation_manager.update_session(
            from_number,
            context=cleaned_response,
            question=follow_up_question
        )

        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return generate_twiml_response(
            "Sorry, something went wrong. Please try again in a moment.",
            status="error"
        )

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

def cleanup_old_audio_files():
    """Clean up audio files older than 1 hour"""
    audio_dir = os.path.join(app.config['STATIC_FOLDER'], 'audio')
    current_time = time.time()
    for filename in os.listdir(audio_dir):
        file_path = os.path.join(audio_dir, filename)
        # Remove files older than 1 hour
        if os.path.getctime(file_path) < (current_time - 3600):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up old audio file: {filename}")
            except Exception as e:
                logger.error(f"Failed to remove old audio file {filename}: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)