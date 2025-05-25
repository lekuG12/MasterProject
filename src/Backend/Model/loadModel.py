from transformers import AutoModelForCausalLM, AutoTokenizer
import os
from decouple import config


def load_model():
    try:
        hf_token = config('HUGGING_FACE_TOKEN')
        gpt_model = config('GPT_MODEL')
        
        if not hf_token or not gpt_model:
            raise ValueError("Missing required environment variables")

        tokenizer = AutoTokenizer.from_pretrained(
            gpt_model,
            use_auth_token=hf_token
        )

        model = AutoModelForCausalLM.from_pretrained(
            gpt_model,
            use_auth_token=hf_token
        )
        
        return tokenizer, model
    except Exception as e:
        raise Exception(f"Failed to load model: {str(e)}")