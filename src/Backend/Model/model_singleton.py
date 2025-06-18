from transformers import pipeline
import logging
import os

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
            try:
                logger.info("Loading model from cache...")
                self._model = pipeline(
                    "text-generation",
                    model="microsoft/DialoGPT-medium",
                    device=-1  # Use CPU, change to 0 for GPU
                )
                logger.info("Model loaded from cache successfully")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                raise RuntimeError(f"Model loading failed: {str(e)}")
        return self._model