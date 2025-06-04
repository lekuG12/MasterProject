from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
import torch
from decouple import config
import logging
import time
import re
from threading import Lock

logger = logging.getLogger(__name__)

class AiModel:
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.model_lock = Lock()
        self.is_loaded = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.generation_config = None

    def load_model(self):
        try:
            hf_token = config('HUGGING_FACE_TOKEN')
            gpt_model = config('GPT_MODEL')
            
            if not hf_token or not gpt_model:
                raise ValueError("Missing required environment variables")
            
            logger.info(f"Loading model: {gpt_model} on {self.device}")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                gpt_model,
                use_auth_token=hf_token,
                padding_side="left"
            )
            
            if not self.tokenizer.pad_token:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            # Load model with device management
            self.model = AutoModelForCausalLM.from_pretrained(
                gpt_model,
                use_auth_token=hf_token,
                torch_dtype=torch.float16 if "cuda" in str(self.device) else torch.float32
            ).to(self.device)
            
            # Set to evaluation mode
            self.model.eval()
            
            # Create generation config
            self.generation_config = GenerationConfig.from_model_config(self.model.config)
            self.generation_config.max_new_tokens = 512
            self.generation_config.temperature = 0.7
            self.generation_config.do_sample = True
            self.generation_config.pad_token_id = self.tokenizer.eos_token_id
            
            self.is_loaded = True
            logger.info(f"Model {gpt_model} loaded successfully")

        except Exception as e:
            logger.exception("Failed to load model")
            raise RuntimeError(f"Model loading failed: {str(e)}")

    def generate_response(self, user_input, conversation_history=None, max_new_tokens=512):
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        start_time = time.time()
        logger.debug(f"Generating response for: {user_input[:50]}...")

        try:
            with self.model_lock:
                # Build context with token length awareness
                context = self._build_context(user_input, conversation_history, max_tokens=1024)
                
                # Tokenize with truncation
                inputs = self.tokenizer(
                    context,
                    return_tensors='pt',
                    truncation=True,
                    max_length=1024
                ).to(self.device)
                
                logger.debug(f"Input token length: {inputs.input_ids.shape[1]}")
                
                # Create generation config for this request
                gen_config = self.generation_config
                gen_config.max_new_tokens = min(max_new_tokens, 1024)
                
                # Generate response
                with torch.inference_mode():
                    outputs = self.model.generate(
                        input_ids=inputs.input_ids,
                        attention_mask=inputs.attention_mask,
                        generation_config=gen_config
                    )
                
                # Extract ONLY the generated portion (after context)
                generated_tokens = outputs[0][inputs.input_ids.shape[1]:]
                response = self.tokenizer.decode(
                    generated_tokens,
                    skip_special_tokens=True
                )
                
                response_time = time.time() - start_time
                cleaned_response = self._clean_response(response)
                logger.info(f"Generated response in {response_time:.2f}s")
                
                return cleaned_response, response_time
        
        except torch.cuda.OutOfMemoryError:
            logger.error("CUDA out of memory - reducing context size")
            torch.cuda.empty_cache()
            return self._fallback_response(user_input), time.time() - start_time
            
        except Exception as e:
            logger.exception("Error generating response")
            return self._fallback_response(user_input), time.time() - start_time

    def _build_context(self, user_input, conversation_history, max_tokens=1024):
        """Build conversation context with token limit awareness"""
        context = "You are a helpful healthcare assistant. Provide concise, professional responses.\n\n"
        token_count = len(self.tokenizer.encode(context))
        
        # Add conversation history in reverse order (newest first)
        if conversation_history:
            history_text = ""
            for conv in reversed(conversation_history[-5:]):  # Last 5 conversations
                conv_str = f"Patient: {conv['user_input']}\nNurse: {conv['bot_response']}\n\n"
                new_tokens = len(self.tokenizer.encode(conv_str))
                
                # Stop if adding this would exceed token limit
                if token_count + new_tokens > max_tokens:
                    break
                    
                history_text = conv_str + history_text
                token_count += new_tokens
            
            context += history_text
        
        # Add current user input
        user_str = f"Patient: {user_input}\nNurse:"
        context += user_str
        
        return context
    
    def _clean_response(self, response):
        """Clean and format the AI response"""
        # Remove any assistant prefixes
        response = re.sub(r"^(Nurse|Assistant):\s*", "", response, flags=re.IGNORECASE)
        
        # Remove trailing incomplete sentences
        response = re.sub(r"[^.!?]*$", "", response).strip()
        
        # Collapse multiple newlines
        response = re.sub(r"\n\s*\n", "\n\n", response)
        
        # Remove any <|endoftext|> tokens
        response = response.replace("<|endoftext|>", "")
        
        # Truncate but preserve complete sentences
        if len(response) > 1500:
            last_punct = max(response[:1500].rfind('.'), 
                            response[:1500].rfind('?'), 
                            response[:1500].rfind('!'))
            response = response[:last_punct+1] + ".." if last_punct > 0 else response[:1497] + "..."
            
        return response.strip()

    def _fallback_response(self, user_input):
        """Fallback responses with medical triage logic"""
        user_input_lower = user_input.lower()
        
        # Medical emergency detection
        emergency_keywords = ['heart attack', 'stroke', 'choking', 'unconscious', 'severe pain', 'chest pain']
        if any(kw in user_input_lower for kw in emergency_keywords):
            return ("⚠️ EMERGENCY ALERT ⚠️\n"
                    "Please call emergency services immediately or go to the nearest ER. "
                    "I've notified our medical team who will contact you shortly.")
                    
        # Other cases
        if any(word in user_input_lower for word in ['help', 'emergency', 'urgent', 'pain']):
            return "I understand you need assistance. A healthcare professional will contact you within 15 minutes."
        elif any(word in user_input_lower for word in ['appointment', 'schedule']):
            return "I can help you schedule an appointment. Please reply with:\n1. Your name\n2. Preferred date/time\n3. Reason for visit"
        elif any(word in user_input_lower for word in ['medication', 'prescription', 'medicine']):
            return "For medication questions, please provide:\n- Medication name\n- Dosage\n- Specific concerns"
        elif any(word in user_input_lower for word in ['thank', 'thanks']):
            return "You're welcome! I'm here to help. Is there anything else I can assist with today?"
        else:
            return "Thank you for your message. A nurse will respond shortly."

# Singleton instance
ai_model = AiModel()

def initialize_model():
    ai_model.load_model()

def get_ai_response(user_input, conversation_history=None):
    return ai_model.generate_response(user_input, conversation_history)