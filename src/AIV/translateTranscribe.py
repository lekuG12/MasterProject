from whispercpp import Whisper
from pydub import AudioSegment
import os

def convert_to_wav(input_file):
    """Convert audio file to WAV format"""
    try:
        # Get the filename without extension
        base_name = os.path.splitext(input_file)[0]
        output_file = f"{base_name}_converted.wav"
        
        # Convert to WAV
        audio = AudioSegment.from_file(input_file)
        audio.export(output_file, format="wav")
        return output_file
    except Exception as e:
        print(f"Error converting to WAV: {e}")
        return None

def transcribe_audio(audio_file):
    """Transcribe audio file using Whisper"""
    try:
        # Initialize Whisper model with English base model
        model = Whisper('base.en')
        
        # Perform transcription
        result = model.transcribe(audio_file)
        return result
    except Exception as e:
        print(f"Error during transcription: {e}")
        return None

if __name__ == "__main__":
    # Replace with your audio file path
    input_audio = "output.wav"
    
    if not os.path.exists(input_audio):
        print(f"File not found: {input_audio}")
    else:
        # Convert to WAV if not already WAV
        if not input_audio.lower().endswith('.wav'):
            wav_file = convert_to_wav(input_audio)
            if not wav_file:
                print("Conversion to WAV failed")
                exit(1)
        else:
            wav_file = input_audio
            
        # Transcribe the WAV file
        result = transcribe_audio(wav_file)
        if result:
            print("Transcription:", result)
        else:
            print("Transcription failed")
            
        # Clean up converted file
        if wav_file != input_audio and os.path.exists(wav_file):
            os.remove(wav_file)