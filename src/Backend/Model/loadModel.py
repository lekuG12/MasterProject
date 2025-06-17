from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
import torch
from decouple import config
import logging
import time
import re
from threading import Lock
from pathlib import Path

logger = logging.getLogger(__name__)

class AiModel:
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.model_lock = Lock()
        self.is_loaded = False
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.generation_config = None
        self.model_name = "microsoft/phi-2"  # Default model

    def load_model(self):
        try:
            logger.info(f"Loading model: {self.model_name} on {self.device}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                padding_side="left",
                model_max_length=1024
            )
            
            # Ensure pad token is set
            if not self.tokenizer.pad_token:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            
            # Set generation config
            self.generation_config = GenerationConfig(
                max_new_tokens=512,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                top_p=0.9,
                top_k=50
            )
            
            self.is_loaded = True
            logger.info(f"Model {self.model_name} loaded successfully")
            return True

        except Exception as e:
            logger.exception("Failed to load model")
            return False

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

# Create singleton instance
ai_model = AiModel()

def initialize_model():
    """Initialize the AI model and tokenizer"""
    return ai_model.load_model()

def get_ai_response(user_input, conversation_history=None, context_history=None):
    """Get AI response with context"""
    if not ai_model.is_loaded:
        raise RuntimeError("Model not initialized. Call initialize_model() first.")
    
    start_time = time.time()
    
    try:
        with ai_model.model_lock:
            # Build context
            context = ai_model._build_context(user_input, conversation_history)
            
            # Generate response
            inputs = ai_model.tokenizer(
                context,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
                padding=True
            ).to(ai_model.device)
            
            with torch.no_grad():
                outputs = ai_model.model.generate(
                    **inputs,
                    generation_config=ai_model.generation_config
                )
            
            response = ai_model.tokenizer.decode(outputs[0], skip_special_tokens=True)
            cleaned_response = ai_model._clean_response(response)
            
            return cleaned_response, time.time() - start_time
            
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return ai_model._fallback_response(user_input), time.time() - start_time