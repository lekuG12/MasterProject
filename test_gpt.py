#!/usr/bin/env python3
"""
Test script to verify the new GPT model is working
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from Backend.Model.model_singleton import ModelSingleton
from Backend.Model.loadModel import get_ai_response

def test_gpt_model():
    """Test the GPT model with a medical question"""
    print("🧪 Testing GPT Model...")
    
    try:
        # Get model instance and force reload
        print("📥 Loading GPT model...")
        model_singleton = ModelSingleton.get_instance()
        model = model_singleton.force_reload()
        print("✅ GPT model loaded successfully")
        
        # Test with a medical question
        test_input = "my baby has a fever of 102 degrees"
        print(f"📝 Testing with input: '{test_input}'")
        
        response, response_time = get_ai_response(test_input)
        
        print(f"✅ Model responded in {response_time:.2f} seconds")
        print(f"🤖 Response: {response}")
        
        if response and response.strip():
            print("✅ GPT model is working correctly!")
            return True
        else:
            print("❌ GPT model returned empty response")
            return False
            
    except Exception as e:
        print(f"❌ Error testing GPT model: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gpt_model()
    if success:
        print("\n🎉 GPT model test passed!")
    else:
        print("\n💥 GPT model test failed!") 