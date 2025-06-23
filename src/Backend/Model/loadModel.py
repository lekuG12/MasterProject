from .model_singleton import ModelSingleton
import logging
import time

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

def get_ai_response(user_input, symptom_history=None):
    """Get response from the AI model, considering all past symptoms."""
    start_time = time.time()
    
    try:
        model_singleton = ModelSingleton.get_instance()
        model = model_singleton.get_model()

        # Combine all reported symptoms for a complete picture
        if symptom_history:
            combined_symptoms = ". ".join(symptom_history)
            input_text = f"Question: A patient presents with the following symptoms: {combined_symptoms}. What is the likely diagnosis and what are the first aid steps?\n\nAnswer:"
        else:
            input_text = f"Question: {user_input}\n\nAnswer:"

        logger.info(f"🤖 Generating response for combined input: {input_text}...")

        # Generate response using a simpler, more robust set of parameters
        response = model(
            input_text,
            max_length=len(input_text.split()) + 150,
            num_return_sequences=1,
            truncation=True
        )

        # Extract and clean the response text
        raw_response = response[0]['generated_text']
        logger.info(f"Raw model output: \"{raw_response}\"")

        bot_response = raw_response
        if input_text in bot_response:
             bot_response = bot_response.split(input_text)[1]
        
        # Further cleanup
        bot_response = bot_response.replace("Answer:", "").strip()
        
        response_time = time.time() - start_time
        
        if not bot_response or bot_response.strip() == "":
            bot_response = "I am sorry, but I could not determine a response. Could you please rephrase your question?"
        
        logger.info(f"✅ Generated response in {response_time:.2f} seconds: {bot_response[:100]}...")
        return bot_response, response_time

    except Exception as e:
        logger.error(f"❌ Error generating AI response: {e}", exc_info=True)
        # Return a fallback response with time
        return ("I apologize, but I'm having trouble processing your request. "
                "Please try again in a moment."), time.time() - start_time