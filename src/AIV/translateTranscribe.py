from gtts import gTTS
from pydub import AudioSegment
from transformers import pipeline
import speech_recognition as sr
import os
import uuid
import time

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
            print(f"Error generating speech: {e}")
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
            print(f"Error cleaning old files: {e}")

    def transcribe_audio(self, audio_file_path):
        """Convert audio to text using speech recognition"""
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_file_path) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)  # Using Google's API
                return text
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None

    def download_audio_from_url(self, audio_url, save_path):
        """Download audio file from URL"""
        try:
            import requests
            response = requests.get(audio_url)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"Error downloading audio: {e}")
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
