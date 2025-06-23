from transformers.pipelines import pipeline
import os
import logging
from pathlib import Path
from decouple import config

logger = logging.getLogger(__name__)

class ModelSingleton:
    _instance = None
    _model = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ModelSingleton()
        return cls._instance

    def get_model(self):
        if self._model is None:
            logger.info("--- Attempting to load AI model ---")
            try:
                model_name = str(config("GPT_MODEL", default="gpt2"))
                auth_token = config("HUGGING_FACE_TOKEN", default=None)

                logger.info(f"Model specified in environment: '{model_name}'")
                if auth_token:
                    logger.info("Hugging Face token FOUND.")
                else:
                    logger.warning("Hugging Face token NOT FOUND. This will fail for private models.")
                
                logger.info(f"Initializing pipeline for model: '{model_name}'...")
                
                self._model = pipeline(
                    "text-generation",
                    model=model_name,
                    token=auth_token,
                    device=-1
                )
                logger.info(f"--- Model '{model_name}' loaded successfully. ---")
            except Exception as e:
                logger.error(f"--- 🔴 FAILED to load model '{model_name}': {e} ---", exc_info=True)
                raise RuntimeError(f"Model loading failed: {str(e)}")
        return self._model

    def clear_cache(self):
        """Clear the model from memory"""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Model cache cleared successfully")
    
    def force_reload(self):
        """Force reload the model (useful when switching models)"""
        self.clear_cache()
        return self.get_model()