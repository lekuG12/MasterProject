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
        self.model_lock = Lock()
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
        

    def generate_response(self, user_input, conversation_history=None, max_length=1024):
        if not self.is_Loaded:
            raise Exception("Model not loaded. Call load_model() first.")
        

        start_time = time.time()

        try:
            with self.model_lock:
                context = self._build_context(user_input, conversation_history)

                inputs = self.tokenizer.encode(
                    context,
                    return_tensors='pt'
                )

                with torch.no_grad():
                    outputs = self.model.generate(
                        inputs,
                        max_length=inputs.shape[1] + max_length,
                        num_return_sequences=1,
                        temperature=0.7,
                        do_sample=True,
                        pad_token_id=self.tokenizer.eos_token_id
                    )
                
                response = self.tokenizer.decode(
                    outputs[0],
                    skip_special_tokens=True
                )

                response = response[len(context):].strip() #extracting only the generated part
                
                response_time = time.time() - start_time
                response = self._clean_response(response)
                logger.info(f"Generated response in {response_time:.2f}s")
                
                return response, response_time
        
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            # Fallback to rule-based response
            return self._fallback_response(user_input), time.time() - start_time
        

    def _build_context(self, user_input, conversation_history):
        """Build conversation context for the model"""
        context = "You are a helpful healthcare assistant. Provide caring, professional responses.\n\n"
        
        if conversation_history:
            for conv in reversed(conversation_history[-3:]):  # Last 3 conversations for context
                context += f"Human: {conv['user_input']}\nAssistant: {conv['bot_response']}\n\n"
        
        context += f"Human: {user_input}\nAssistant:"
        return context
    
    
    def _clean_response(self, response):
        """Clean and format the AI response"""
        # Remove potential repetitions and clean formatting
        response = response.split('\n')[0]  # Take first line
        response = response.strip()
        
        # Limit response length for SMS
        if len(response) > 1500:
            response = response[:1500] + "..."
            
        return response
    

    def _fallback_response(self, user_input):
        """Fallback rule-based responses when AI model fails"""
        user_input_lower = user_input.lower()
        
        if any(word in user_input_lower for word in ['help', 'emergency', 'urgent', 'pain']):
            return "I understand you need assistance. A healthcare professional will contact you shortly. For medical emergencies, please call 911 immediately."
        elif any(word in user_input_lower for word in ['appointment', 'schedule']):
            return "I can help you schedule an appointment. Please let me know your preferred date and time."
        elif any(word in user_input_lower for word in ['medication', 'prescription', 'medicine']):
            return "For medication questions, please consult your healthcare provider. I can help schedule a consultation if needed."
        elif any(word in user_input_lower for word in ['thank', 'thanks']):
            return "You're welcome! I'm here to help. Is there anything else I can assist you with?"
        else:
            return "Thank you for your message."



ai_model = Model()

def initialize_model():
    """Initialize the AI model"""
    ai_model.load_model()

def get_ai_response(user_input, conversation_history=None):
    """Get AI response - main interface function"""
    return ai_model.generate_response(user_input, conversation_history)