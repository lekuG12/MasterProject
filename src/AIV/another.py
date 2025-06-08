import torch
import soundfile as sf
import os
from urllib.error import URLError
import time

def load_tts_model(max_retries=3, retry_delay=5):
    """Load the Silero TTS model with retry logic"""
    for attempt in range(max_retries):
        try:
            model, example_text = torch.hub.load(
                repo_or_dir='snakers4/silero-models',
                model='silero_tts',
                language='en',
                speaker='v3_en'
            )
            return model
        except URLError as e:
            print(f"Network error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Failed to download model. Checking for cached version...")
                # Try to load from cache
                cache_dir = os.path.join(torch.hub.get_dir(), 'snakers4_silero-models_master')
                if os.path.exists(cache_dir):
                    return torch.hub.load(
                        repo_or_dir=cache_dir,
                        model='silero_tts',
                        language='en',
                        speaker='v3_en',
                        source='local'
                    )
                raise RuntimeError("Could not load model: No internet connection and no cached version available")

def generate_speech(text, output_file='output.wav', sample_rate=48000):
    """Generate speech from text and save to file"""
    try:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {device}")

        model = load_tts_model()
        model.to(device)

        audio = model.apply_tts(
            text=text,
            speaker='en_0',
            sample_rate=sample_rate
        )

        sf.write(output_file, audio.cpu().numpy(), sample_rate)
        print(f"Audio saved to: {output_file}")
        return True

    except Exception as e:
        print(f"Error generating speech: {e}")
        return False

if __name__ == "__main__":
    text = "Assessment: poorly treated malaria / sepsis First Aid: cool compresses. Seek emergency help. Note: For severe symptoms, immediate medical attention is crucial."
    generate_speech(text)
