from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
import torch
from decouple import config
import logging
import time
import re
from threading import Lock
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

class AiModel:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_lock = Lock()
        self.is_loaded = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Primary and fallback model configuration
        self.primary_model = config('GPT_MODEL')
        self.fallback_model = "gpt2"
        self.hf_token = config('HUGGING_FACE_TOKEN')

    def load_model(self):
        try:
            # Try loading primary model first
            logger.info(f"Attempting to load primary model: {self.primary_model}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.primary_model,
                    use_auth_token=self.hf_token
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.primary_model,
                    use_auth_token=self.hf_token,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto"
                )
            except Exception as e:
                logger.warning(f"Primary model failed to load: {e}. Falling back to GPT-2")
                # Load fallback model (GPT-2)
                self.tokenizer = AutoTokenizer.from_pretrained(self.fallback_model)
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.fallback_model,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto"
                )

            # Ensure pad token is set
            if not self.tokenizer.pad_token:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.is_loaded = True
            logger.info("Model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load any model: {str(e)}")
            return False

    def generate_response(self, user_input, conversation_history=None):
        if not self.is_loaded:
            return "I'm currently initializing. Please try again in a moment.", 0

        start_time = time.time()
        try:
            with self.model_lock:
                # Prepare prompt
                prompt = self._build_prompt(user_input, conversation_history)
                
                # Tokenize input
                inputs = self.tokenizer(
                    prompt,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True
                ).to(self.device)

                # Generate response
                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=256,
                        temperature=0.7,
                        do_sample=True,
                        pad_token_id=self.tokenizer.pad_token_id,
                        eos_token_id=self.tokenizer.eos_token_id
                    )

                response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                cleaned_response = self._clean_response(response, prompt)
                return cleaned_response, time.time() - start_time

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._fallback_response(), time.time() - start_time

    def _build_prompt(self, user_input, conversation_history=None):
        base_prompt = "You are a helpful healthcare assistant. Please provide a professional response.\n\n"
        if conversation_history and len(conversation_history) > 0:
            # Add last 2 conversations for context
            for conv in conversation_history[-2:]:
                base_prompt += f"User: {conv['user_input']}\nAssistant: {conv['bot_response']}\n\n"
        base_prompt += f"User: {user_input}\nAssistant:"
        return base_prompt

    def _clean_response(self, response, original_prompt):
        # Remove the prompt from the response
        response = response.replace(original_prompt, "")
        # Remove any remaining assistant/user prefixes
        response = re.sub(r"^(Assistant|User):\s*", "", response)
        # Clean up whitespace
        response = response.strip()
        return response

    def _fallback_response(self):
        return "I apologize, but I'm having trouble processing your request. Please try again or contact our healthcare team directly."

# Create singleton instance
ai_model = AiModel()

def initialize_model():
    """Initialize the AI model"""
    return ai_model.load_model()

def get_ai_response(user_input, conversation_history=None, context_history=None):
    """Get AI response with context"""
    return ai_model.generate_response(user_input, conversation_history)

def clear_model_cache():
    """Clear the Hugging Face cache directory"""
    try:
        cache_dir = Path.home() / ".cache" / "huggingface"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info("Successfully cleared Hugging Face cache")
        return True
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return False