import os
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_model_cache():
    """Setup and initialize model cache"""
    # Set up cache directory
    cache_dir = Path('D:/Smoke_IT/MasterProject/model_cache')
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Set environment variables
    os.environ['TRANSFORMERS_CACHE'] = str(cache_dir)
    os.environ['HF_HOME'] = str(cache_dir)
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
    
    try:
        logger.info("Downloading and caching model...")
        model_name = "microsoft/DialoGPT-medium"
        
        # Download and cache the model and tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        model = AutoModelForCausalLM.from_pretrained(model_name, cache_dir=cache_dir)
        
        logger.info(f"Model cached successfully in {cache_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}")
        return False

if __name__ == "__main__":
    setup_model_cache()