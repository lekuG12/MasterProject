from gtts import gTTS
from pydub import AudioSegment
from transformers import pipeline
import speech_recognition as sr
import os
import uuid
import time
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse
from decouple import config
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, static_dir=None):
        self.static_dir = static_dir or os.path.join(os.path.dirname(__file__), '..', 'Backend', 'FlaskAPI', 'static', 'audio')
        os.makedirs(self.static_dir, exist_ok=True)

    def generate_speech(self, text, phone_number=None):
        """Generate speech from text with status updates"""
        try:
            # Notify start of process
            status_msg = "🎯 Generating your voice response..."
            logger.info(status_msg)
            
            # Create unique filename
            filename = f"response_{phone_number.split(':')[-1]}_{uuid.uuid4().hex[:8]}.mp3"
            file_path = os.path.join(self.static_dir, filename)

            # Generate MP3
            logger.info("🔊 Converting text to speech...")
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(file_path)

            # Optimize audio
            logger.info("⚡ Optimizing audio quality...")
            audio = AudioSegment.from_mp3(file_path)
            normalized_audio = audio.normalize()
            
            # Export with optimized settings
            logger.info("💾 Saving optimized audio...")
            normalized_audio.export(
                file_path,
                format="mp3",
                parameters=["-q:a", "0", "-b:a", "128k"]
            )

            logger.info("✅ Voice response ready!")
            return filename

        except Exception as e:
            logger.error(f"❌ Error generating speech: {e}")
            return None

    def clean_old_files(self, max_age_hours=24):
        """Clean up old audio files"""
        try:
            current_time = time.time()
            for filename in os.listdir(self.static_dir):
                file_path = os.path.join(self.static_dir, filename)
                if os.path.getmtime(file_path) < (current_time - max_age_hours * 3600):
                    os.remove(file_path)
        except Exception as e:
            logger.error(f"Error cleaning old files: {e}")

    def transcribe_audio(self, audio_file_path):
        """Convert audio to text with status updates"""
        try:
            logger.info("🎤 Processing your voice message...")
            audio = AudioSegment.from_file(audio_file_path)
            
            # Create temporary WAV file
            temp_wav = os.path.join(
                os.path.dirname(audio_file_path),
                f"temp_{int(time.time())}.wav"
            )
            
            logger.info("🔄 Converting audio format...")
            audio.export(
                temp_wav,
                format="wav",
                parameters=[
                    "-ac", "1",
                    "-ar", "16000",
                    "-sample_fmt", "s16"
                ]
            )
            
            # Initialize recognizer
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8
            
            try:
                with sr.AudioFile(temp_wav) as source:
                    logger.info("👂 Listening to your message...")
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    logger.info("📝 Converting speech to text...")
                    audio_data = recognizer.record(source)
                    
                    text = recognizer.recognize_google(audio_data, language='en-US')
                    logger.info("✅ Successfully converted your voice to text!")
                    
                    return text.strip()
                    
            finally:
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
                    
        except Exception as e:
            logger.error(f"❌ Error processing voice message: {str(e)}")
            return None

    def download_audio_from_url(self, audio_url, save_path):
        """Download audio with progress updates"""
        try:
            logger.info("📥 Receiving your voice message...")
            
            # Set up retry strategy
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )

            # Create session with retry strategy
            session = requests.Session()
            session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
            session.mount("http://", HTTPAdapter(max_retries=retry_strategy))

            # Add Twilio authentication
            auth = (os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
            
            # Set up headers with auth
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'audio/*, application/octet-stream'
            }

            logger.info(f"Attempting to download audio from: {audio_url}")
            
            # Download the file with authentication
            response = session.get(
                audio_url,
                auth=auth,
                stream=True,
                timeout=60,
                headers=headers
            )
            response.raise_for_status()

            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Download with progress tracking
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded_size = 0

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size:
                            progress = (downloaded_size / total_size) * 100
                            if progress % 25 == 0:  # Update every 25%
                                logger.info(f"📊 Download progress: {progress:.0f}%")

            # Verify downloaded file
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                file_size = os.path.getsize(save_path)
                logger.info(f"Successfully downloaded audio file ({file_size} bytes)")
                return True
            else:
                logger.error("Downloaded file is empty or missing")
                return False

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Authentication failed. Check Twilio credentials.")
            else:
                logger.error(f"HTTP error occurred: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error downloading audio: {str(e)}", exc_info=True)
            return False
        finally:
            session.close()

    def clean_response(self, text):
        """Clean up the AI response by removing artifacts and formatting the output"""
        try:
            # Remove all text within square brackets
            cleaned_text = re.sub(r'\[.*?\]', '', text)
            
            # Split into sections
            sections = cleaned_text.split('\n')
            formatted_response = []
            
            current_section = None
            for line in sections:
                line = line.strip()
                if not line:
                    continue
                    
                # Handle section headers
                if line.lower().startswith('diagnosis:'):
                    current_section = 'diagnosis'
                    formatted_response.append("*Diagnosis*:")
                    continue
                elif line.lower().startswith('first aid'):
                    current_section = 'first_aid'
                    formatted_response.append("\n*First Aid Steps*:")
                    continue
                    
                # Clean and format line content
                line = re.sub(r'ptoms:|symptoms:', '', line, flags=re.IGNORECASE)
                line = re.sub(r'^\s*[•●]\s*', '• ', line)  # Standardize bullet points
                
                # Add line to appropriate section
                if current_section == 'diagnosis':
                    if not line.startswith('*'):
                        formatted_response.append(line)
                elif current_section == 'first_aid':
                    if line.lower().startswith('urgent') or 'immediate' in line.lower():
                        urgent_message = "\n⚠ URGENT: " + line.split(':')[-1].strip()
                        formatted_response.append(urgent_message)
                    elif not line.startswith(('*', '⚠')):
                        formatted_response.append(f"• {line.strip('•').strip()}")
            
            # Add conversational ending
            formatted_response.append("\nHave you tried any remedies so far?")
            
            return '\n'.join(formatted_response)
            
        except Exception as e:
            logger.error(f"Error cleaning response: {str(e)}")
            return text  # Return original text if cleaning fails

class SpeechConverter:
    def __init__(self, temp_dir="temp_audio"):
        self.recognizer = sr.Recognizer()
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)

    def text_to_speech(self, text, filename="output", format="mp3"):
        mp3_path = os.path.join(self.temp_dir, f"{filename}.mp3")
        tts = gTTS(text)
        tts.save(mp3_path)

        if format == "mp3":
            return mp3_path
        elif format == "ogg":
            ogg_path = os.path.join(self.temp_dir, f"{filename}.ogg")
            audio = AudioSegment.from_mp3(mp3_path)
            audio.export(ogg_path, format="ogg", codec="libopus")
            return ogg_path
        else:
            raise ValueError("Unsupported format. Choose 'mp3' or 'ogg'.")

    def speech_to_text(self, audio_path):
        # Convert to WAV (SpeechRecognition prefers WAV)
        audio = AudioSegment.from_file(audio_path)
        wav_path = os.path.join(self.temp_dir, "temp.wav")
        audio.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio_data = self.recognizer.record(source)
            try:
                text = self.recognizer.recognize_google(audio_data)
                return text
            except sr.UnknownValueError:
                return "Could not understand audio."
            except sr.RequestError as e:
                return f"API request error: {e}"
            finally:
                os.remove(wav_path)

# Example usage
if __name__ == "__main__":
    converter = SpeechConverter()

    # Text to speech
    audio_file = converter.text_to_speech("Hello, this is a demo!", format="ogg")
    print(f"Audio saved at: {audio_file}")

    # Speech to text
    transcription = converter.speech_to_text(audio_file)
    print(f"Transcribed text: {transcription}")
