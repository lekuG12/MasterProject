from gtts import gTTS
from pydub import AudioSegment
from transformers import pipeline
import speech_recognition as sr
import os
import uuid
import time
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, static_dir=None):
        self.static_dir = static_dir or os.path.join(os.path.dirname(__file__), '..', 'Backend', 'FlaskAPI', 'static', 'audio')
        os.makedirs(self.static_dir, exist_ok=True)

    def generate_speech(self, text, phone_number=None):
        """
        Generate speech from text and save as audio file
        Returns: filename of the generated audio
        """
        try:
            # Create unique filename using phone number if provided
            filename = f"response_{phone_number.split(':')[-1]}_{uuid.uuid4().hex[:8]}.mp3"
            file_path = os.path.join(self.static_dir, filename)

            # Generate MP3 using gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(file_path)

            # Convert to proper format and optimize
            audio = AudioSegment.from_mp3(file_path)
            
            # Normalize audio levels
            normalized_audio = audio.normalize()
            
            # Export with optimized settings
            normalized_audio.export(
                file_path,
                format="mp3",
                parameters=["-q:a", "0", "-b:a", "128k"]
            )

            return filename

        except Exception as e:
            logger.error(f"Error generating speech: {e}")
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
        """Convert audio to text using speech recognition"""
        try:
            recognizer = sr.Recognizer()
            
            # Adjust recognition parameters
            recognizer.energy_threshold = 300  # Increase sensitivity
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8  # Shorter pause threshold
            
            with sr.AudioFile(audio_file_path) as source:
                logger.info("Reading audio file")
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                logger.info("Recording audio data")
                audio_data = recognizer.record(source)
                
                logger.info("Starting transcription")
                # Try multiple recognition attempts with different APIs
                try:
                    text = recognizer.recognize_google(audio_data, language='en-US')
                    logger.info("Successfully transcribed using Google Speech Recognition")
                except:
                    try:
                        text = recognizer.recognize_sphinx(audio_data)
                        logger.info("Successfully transcribed using Sphinx")
                    except:
                        logger.error("All transcription attempts failed")
                        return None
                        
                return text.strip()
                
        except Exception as e:
            logger.error(f"Error in transcribe_audio: {str(e)}", exc_info=True)
            return None

    def download_audio_from_url(self, audio_url, save_path):
        """Download audio file from URL with comprehensive error handling"""
        try:
            # Set up headers to mimic a browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            # Make request with extended timeout and headers
            response = requests.get(
                audio_url,
                stream=True,
                timeout=60,
                headers=headers,
                verify=True  # Enable SSL verification
            )
            response.raise_for_status()

            # Verify content type
            content_type = response.headers.get('content-type', '')
            if not any(audio_type in content_type.lower() for audio_type in ['audio/', 'application/octet-stream']):
                logger.error(f"Invalid content type received: {content_type}")
                return False

            # Ensure the directory exists
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
                            logger.debug(f"Download progress: {progress:.1f}%")

            # Verify downloaded file
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                logger.info(f"Successfully downloaded audio ({os.path.getsize(save_path)} bytes) to {save_path}")
                return True
            else:
                logger.error("Downloaded file is empty or missing")
                return False

        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Certificate error: {str(e)}")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            return False
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timed out: {str(e)}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Download error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while downloading audio: {str(e)}", exc_info=True)
            return False

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
