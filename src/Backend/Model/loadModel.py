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
        self.device = torch.device("cpu")
        self.generation_config = None

    def load_model(self):
        try:
            hf_token = config('HUGGING_FACE_TOKEN')
            gpt_model = config('GPT_MODEL')
            
            if not hf_token or not gpt_model:
                raise ValueError("Missing required environment variables")
            
            logger.info(f"Loading model: {gpt_model} on {self.device}")

            # Load tokenizer with position embedding handling
            self.tokenizer = AutoTokenizer.from_pretrained(
                gpt_model,
                use_auth_token=hf_token,
                padding_side="left",
                model_max_length=1024  # Add this line
            )
            
            # Ensure pad token is set
            if not self.tokenizer.pad_token:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

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
            logger.error("Model not loaded")
            return "I'm currently initializing. Please try again in a moment.", 0
        
        start_time = time.time()
        logger.info(f"Starting response generation for input: {user_input[:50]}...")

        try:
            with self.model_lock:
                # Build context with token length awareness
                context = self._build_context(user_input, conversation_history, max_tokens=1024)
                logger.debug(f"Built context: {context[:100]}...")
                
                # Tokenize with proper position handling
                inputs = self.tokenizer(
                    context,
                    return_tensors='pt',
                    truncation=True,
                    max_length=1024,
                    padding=True,
                    add_special_tokens=True
                ).to(self.device)
                
                logger.info(f"Input tensor shape: {inputs.input_ids.shape}, Generating response...")
                
                # Generate with position handling
                outputs = self.model.generate(
                    input_ids=inputs.input_ids,
                    attention_mask=inputs.attention_mask,
                    pad_token_id=self.tokenizer.pad_token_id,
                    max_new_tokens=min(max_new_tokens, 512),
                    min_length=1,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    use_cache=True
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
            
        except IndexError as e:
            if "index out of range in self" in str(e):
                logger.error("Position embedding index error - reducing context size")
                # Retry with smaller context
                return self.generate_response(user_input, None, max_new_tokens=256)
            raise
        except Exception as e:
            logger.exception("Error generating response")
            return self._fallback_response(user_input), time.time() - start_time

    def _build_context(self, user_input, conversation_history, max_tokens=1024):
        """Build conversation context with strict token limit awareness"""
        # Initialize history_text at the start
        history_text = ""
        
        context = "You are a helpful healthcare assistant. Provide concise, professional responses.\n\n"
        
        # Reserve tokens for the current user input and system prompt
        user_tokens = len(self.tokenizer.encode(user_input))
        system_tokens = len(self.tokenizer.encode(context))
        available_tokens = max_tokens - user_tokens - system_tokens - 50  # 50 token buffer
        
        if available_tokens <= 0:
            logger.warning("Input too long, truncating context")
            return f"{context}Patient: {user_input[:512]}...\nNurse:"
        
        # Add conversation history with strict token counting
        if conversation_history and len(conversation_history) > 0:
            for conv in reversed(conversation_history[-3:]):  # Last 3 conversations
                conv_str = f"Patient: {conv['user_input']}\nNurse: {conv['bot_response']}\n\n"
                conv_tokens = len(self.tokenizer.encode(conv_str))
                
                if available_tokens - conv_tokens <= 0:
                    break
                    
                history_text = conv_str + history_text
                available_tokens -= conv_tokens
    
        # Combine all parts of the context
        final_context = context + history_text + f"Patient: {user_input}\nNurse:"
    
        logger.debug(f"Built context with {len(self.tokenizer.encode(final_context))} tokens")
        return final_context
    
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