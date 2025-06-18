from .model_singleton import ModelSingleton
import logging
import time
import re

logger = logging.getLogger(__name__)

def initialize_model():
    """Get or initialize the model singleton"""
    try:
        model_singleton = ModelSingleton.get_instance()
        model_singleton.get_model()
        return True
    except Exception as e:
        logger.error(f"Model initialization failed: {e}")
        return False

def clear_model_cache():
    """Clear the model from memory if needed"""
    try:
        model_singleton = ModelSingleton.get_instance()
        model_singleton.clear_cache()
        return True
    except Exception as e:
        logger.error(f"Failed to clear model cache: {e}")
        return False

def get_ai_response(user_input, conversation_history=None, context=None):
    """Get response from the AI model"""
    try:
        model_singleton = ModelSingleton.get_instance()
        model = model_singleton.get_model()
        # ... rest of your response generation code ...
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return "I apologize, but I'm having trouble processing your request. Please try again or contact our healthcare team directly."