from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

from decouple import config
import logging
import time
from threading import Lock


logger = logging.getLogger(__name__)


class Model:
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.model = Lock()
        self.is_Loaded = False


    def load_model(self):
        try:
            hf_token = config('HUGGING_FACE_TOKEN')
            gpt_model = config('GPT_MODEL')
            
            if not hf_token or not gpt_model:
                raise ValueError("Missing required environment variables")
            
            logger.info(f"Loading model: {gpt_model}")

            self.tokenizer = AutoTokenizer.from_pretrained(
                gpt_model,
                use_auth_token=hf_token,
                padding_side="left"
            )

            if self.tokenizer.pad_token_type_id is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model = AutoModelForCausalLM.from_pretrained(
                gpt_model,
                use_auth_token=hf_token
            )
            
            self.is_Loaded = True
            logger.info(f"Model {gpt_model} loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise Exception(f"Failed to load model: {str(e)}")
        

    def