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
import requests

from Backend.database.data import db, init_database, save_conversation, get_conversation_history
from Backend.Model.loadModel import initialize_model, clear_model_cache, get_ai_response
from Backend.Model.conversation_state import get_conversation_state, ConversationStateType
from Backend.Model.conversation_patterns import UserIntent
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

def get_ngrok_url():
    """Try to get the current ngrok URL automatically"""
    try:
        response = requests.get('http://localhost:4040/api/tunnels', timeout=3)
        if response.status_code == 200:
            tunnels = response.json()
            if tunnels and 'tunnels' in tunnels:
                for tunnel in tunnels['tunnels']:
                    if tunnel['proto'] == 'https':
                        return tunnel['public_url']
        return None
    except:
        return None

# Configure BASE_URL - use the provided ngrok URL directly
base_url = 'https://394e41f97a55.ngrok-free.app'
logger.info(f"Using ngrok URL: {base_url}")

app.config['BASE_URL'] = base_url
logger.info(f"Configured BASE_URL: {base_url}")

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
    """
    Cleans the raw AI model output by intelligently parsing multi-line
    diagnosis and first-aid sections, removing duplicates and gibberish,
    and ensuring diagnosis does not contain first-aid instructions.
    """
    logger.info(f"Cleaning raw response: \"{text[:200]}...\"")

    # 1. Initial cleanup
    text = re.sub(r'\[.*?\]', '', text).strip()
    text = text.replace("Answer:", "").strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # 2. State-machine based parsing
    diagnosis_lines = []
    first_aid_lines = []
    current_section = None

    # Keywords that indicate first-aid advice
    first_aid_keywords = [
        "rest", "hydration", "paracetamol", "monitor", "seek medical", "evaluation",
        "raise head", "saline", "keep warm", "offer fluids", "cool environment",
        "sponge", "ors", "lay flat", "elevated", "urgent care", "nasal drops", "spray"
    ]

    for line in lines:
        line = re.sub(r'\s{2,}', ' ', line).strip()
        if not line:
            continue

        if line.lower().startswith("diagnosis:"):
            current_section = "diagnosis"
            diag_text = line.split(":", 1)[1].strip()
            if diag_text:
                diagnosis_lines.append(diag_text)
            continue
        elif line.lower().startswith("first aid:"):
            current_section = "first_aid"
            aid_text = line.split(":", 1)[1].strip()
            if aid_text:
                first_aid_lines.append(aid_text)
            continue

        if current_section == "diagnosis":
            # Exclude lines that look like first-aid advice
            if not any(kw in line.lower() for kw in first_aid_keywords):
                diagnosis_lines.append(line)
        elif current_section == "first_aid":
            first_aid_lines.append(line)
        elif current_section is None:
            # Only add to diagnosis if not first-aid advice
            if not any(kw in line.lower() for kw in first_aid_keywords):
                diagnosis_lines.append(line)

    # 3. Process diagnosis
    full_diagnosis = " ".join(diagnosis_lines) if diagnosis_lines else "No specific diagnosis provided. Please describe the symptoms."

    # 4. Clean first aid steps
    unique_steps = []
    seen_steps = set()
    emergency_added = False
    for step in first_aid_lines:
        # Remove gibberish (repeated 'ptoms', etc.)
        if re.search(r'(ptoms){2,}', step.lower()):
            continue
        # Normalize step for deduplication
        norm_step = step.lower().strip('.')
        # Only keep one emergency response
        if any(kw in norm_step for kw in [
            "seek emergency care", "urgent care", "seek emergency medical care", "seek medical evaluation"
        ]):
            if not emergency_added:
                unique_steps.append("Seek medical evaluation immediately.")
                emergency_added = True
            continue
        # Deduplicate
        if norm_step not in seen_steps and len(step) > 3:
            unique_steps.append(step)
            seen_steps.add(norm_step)

    # 5. Assemble the final response
    cleaned_text = f"*Diagnosis*:\n{full_diagnosis}"
    if unique_steps:
        cleaned_text += "\n\n*First Aid Steps*:"
        for step in unique_steps:
            cleaned_text += f"\n• {step}"

    logger.info(f"Cleaned response: \"{cleaned_text[:200]}...\"")
    return cleaned_text

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
    """Handle incoming WhatsApp messages using a state machine."""
    logger.info("--- Webhook request received ---")
    try:
        from_number = request.form.get('From', '')
        user_input = request.form.get('Body', '').strip() if request.form.get('Body') else None

        # If no text, check for audio
        if not user_input:
            num_media = int(request.form.get('NumMedia', 0))
            if num_media > 0 and request.form.get('MediaContentType0', '').startswith('audio/'):
                media_url = request.form.get('MediaUrl0')
                content_type = request.form.get('MediaContentType0')
                logger.info(f"Audio message detected. Media URL: {media_url}, Content-Type: {content_type}")
                # Download and transcribe audio
                temp_audio_path = os.path.join(app.config['STATIC_FOLDER'], 'temp', f"input_{from_number.replace('+','')}.ogg")
                try:
                    if not tts_service.download_audio_from_url(media_url, temp_audio_path):
                        logger.error("Failed to download audio file.")
                        external_send_message(from_number, "Sorry, I couldn't download your audio message.")
                        return Response("OK", status=200)
                    user_input = tts_service.transcribe_audio(temp_audio_path)
                    logger.info(f"[AUDIO->TEXT] Transcribed audio to text: '{user_input}'")
                    logger.info(f"Transcribed audio to: {user_input}")
                except Exception as e:
                    logger.error(f"Audio processing failed: {e}")
                    external_send_message(from_number, "Sorry, I couldn't process your audio message.")
                    return Response("OK", status=200)
                finally:
                    if os.path.exists(temp_audio_path):
                        os.remove(temp_audio_path)
            else:
                logger.warning("Request missing From or Body or valid audio. Aborting.")
                return Response("Request incomplete", status=400)
        
        if not from_number or not user_input:
            logger.warning("Request missing From or Body. Aborting.")
            return Response("Request incomplete", status=400)
        
        session_state = get_conversation_state(from_number)
        logger.info(f"User {from_number} is in state: {session_state.type.name}")

        # Respond to greetings before any state logic
        if UserIntent.is_greeting(user_input):
            external_send_message(
                to_number=from_number,
                body_text="Hello! Please describe your child's symptoms and I'll help you with a diagnosis and first aid advice."
            )
            return Response("OK", status=200)

        # --- State Machine Logic ---
        if session_state.type == ConversationStateType.COLLECTING_SYMPTOMS:
            if UserIntent.is_negative(user_input):
                symptom_summary = session_state.get_all_symptoms()
                logger.info(f"User finished. Generating diagnosis for: '{symptom_summary}'")
                
                if not symptom_summary.strip():
                    external_send_message(from_number, "Please describe at least one symptom before I can help.")
                    session_state.reset()
                    return Response("OK", status=200)

                try:
                    bot_response, _ = get_ai_response(symptom_summary)
                    logger.info(f"Raw model output: {bot_response}")
                except Exception as e:
                    logger.error(f"Model generation failed: {e}")
                    external_send_message(from_number, "Sorry, I couldn't generate a diagnosis at this time.")
                    session_state.reset()
                    return Response("OK", status=200)

                try:
                    cleaned_response = clean_response(bot_response)
                    logger.info(f"Cleaned response: {cleaned_response}")
                except Exception as e:
                    logger.error(f"Response cleaning failed: {e}")
                    external_send_message(from_number, "Sorry, I couldn't process the diagnosis output.")
                    session_state.reset()
                    return Response("OK", status=200)

                logger.info("Sending final diagnosis text and audio...")
                try:
                    audio_filename = tts_service.generate_speech(cleaned_response, from_number)
                    if audio_filename:
                        audio_path = os.path.join(app.config['STATIC_FOLDER'], 'audio', audio_filename)
                        if os.path.exists(audio_path):
                            logger.info(f"Audio file generated: {audio_path} ({os.path.getsize(audio_path)} bytes)")
                        else:
                            logger.error(f"Audio file {audio_path} does not exist after generation!")
                    else:
                        logger.error("Audio filename is None after generation!")
                except Exception as e:
                    logger.error(f"Audio generation failed: {e}")
                    audio_filename = None

                # Try to send both text and audio, fallback to text if audio fails
                try:
                    if audio_filename and os.path.exists(os.path.join(app.config['STATIC_FOLDER'], 'audio', audio_filename)):
                        logger.info("Attempting to send paired text and audio response...")
                        success, status = send_paired_response(from_number, cleaned_response, audio_filename)
                        logger.info(f"send_paired_response returned: success={success}, status={status}")
                        if not success:
                            logger.warning("Paired response failed, falling back to text-only.")
                            external_send_message(from_number, cleaned_response)
                    else:
                        logger.warning("Audio not available, sending text-only response.")
                        external_send_message(from_number, cleaned_response)
                except Exception as e:
                    logger.error(f"Sending response failed: {e}")
                    external_send_message(from_number, cleaned_response)
                
                session_state.reset()
                logger.info(f"Conversation for {from_number} has been reset.")
                return Response("OK", status=200)
            else:
                session_state.add_symptom(user_input)
                logger.info(f"Added new symptom. History: {session_state.symptom_history}")
                external_send_message(
                    to_number=from_number,
                    body_text="Got it. If you’re finished listing symptoms, reply with ‘no’ or ‘that’s all’. Otherwise, add more symptoms."
                )
        else: # GREETING state
            session_state.reset()
            session_state.add_symptom(user_input)
            session_state.type = ConversationStateType.COLLECTING_SYMPTOMS
            logger.info(f"New conversation started. First symptom: '{user_input}'")
            external_send_message(to_number=from_number, body_text="I've noted that. Is there anything else about the symptoms?")
            
        return Response("OK", status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return Response("Server error", status=500)

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve audio files with proper headers and error handling"""
    try:
        # Log the request for debugging
        logger.info(f"🎵 Audio request received for: {filename}")
        logger.info(f"📡 Request from: {request.remote_addr}")
        logger.info(f"🔗 Full URL: {request.url}")
        logger.info(f"📋 Request headers: {dict(request.headers)}")
        
        safe_filename = os.path.basename(filename)
        audio_path = os.path.join(app.config['STATIC_FOLDER'], 'audio', safe_filename)
        
        logger.info(f"📁 Looking for audio file at: {audio_path}")
        
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            logger.info(f"✅ Audio file found, size: {file_size} bytes")
            
            # Set proper headers for audio streaming
            response = send_file(
                audio_path,
                mimetype='audio/mpeg',
                as_attachment=False,
                download_name=safe_filename
            )
            
            # Add CORS headers for Twilio
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Content-Length'] = str(file_size)
            
            logger.info(f"✅ Successfully serving audio file: {safe_filename}")
            logger.info(f"📊 Response headers: {dict(response.headers)}")
            return response
        else:
            logger.error(f"❌ Audio file not found: {audio_path}")
            return Response("Audio file not found", status=404, mimetype='text/plain')
            
    except Exception as e:
        logger.error(f"❌ Error serving audio {filename}: {e}", exc_info=True)
        return Response(f"Error serving audio: {str(e)}", status=500, mimetype='text/plain')

@app.route('/audio/<filename>', methods=['OPTIONS'])
def audio_options(filename):
    """Handle CORS preflight requests for audio files"""
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

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

def send_paired_response(to_number, text_response, audio_filename):
    """Send both text and audio responses as a pair, with robust logging."""
    try:
        logger.info(f"Starting paired response for {to_number}")
        # Send text response first
        text_result = external_send_message(
            to_number=to_number,
            body_text=text_response,
            message_type='whatsapp'
        )
        logger.info(f"Text message sent successfully: {text_result}")
        # Prepare audio response
        base_url = app.config['BASE_URL']
        audio_url = f"{base_url}/audio/{audio_filename}"
        audio_path = os.path.join(app.config['STATIC_FOLDER'], 'audio', audio_filename)
        logger.info(f"Audio URL: {audio_url}")
        logger.info(f"Audio path: {audio_path}")
        # Verify audio file exists and has content
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found at {audio_path}")
            return False, 'audio_file_missing'
        file_size = os.path.getsize(audio_path)
        if file_size == 0:
            logger.error(f"Audio file is empty: {audio_path}")
            return False, 'audio_file_empty'
        logger.info(f"Audio file verified: {file_size} bytes")
        # Send audio response
        try:
            audio_result = twilio_client.messages.create(
                from_='whatsapp:+14155238886',
                to=to_number,
                media_url=[audio_url]
            )
            logger.info(f"Audio message sent successfully: {audio_result.sid}")
            logger.info(f"Paired response completed. Text: {text_result}, Audio: {audio_result.sid}")
            return True, 'sent_paired'
        except Exception as e:
            logger.error(f"Failed to send audio message: {e}")
            return False, 'audio_send_failed'
    except Exception as e:
        logger.error(f"Failed to send paired response: {e}", exc_info=True)
        return False, 'failed'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)