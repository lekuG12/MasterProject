import shutil
import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_model_cache():
    """Download and cache the model fresh"""
    try:
        # Clear the transformers cache
        cache_dir = os.path.expanduser('~/.cache/huggingface/transformers')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            logger.info("Cleared existing transformers cache")
        
        # Download and cache the model fresh
        logger.info("Downloading model...")
        model_name = "microsoft/DialoGPT-medium"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)
        
        logger.info("Model downloaded and cached successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to reset model: {e}")
        return False

if __name__ == "__main__":
    reset_model_cache()