from gtts import gTTS
from pydub import AudioSegment
import speech_recognition as sr
import os

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
