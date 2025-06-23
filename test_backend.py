#!/usr/bin/env python3
"""
A simple script to test the Flask backend directly, bypassing Twilio.
"""

import requests

def test_webhook():
    """
    Sends a simulated WhatsApp message to the local Flask server.
    """
    print("--- 🚀 Sending test request to backend ---")
    
    # The URL for your local webhook
    url = "http://localhost:5000/webhook"
    
    # The data we are sending, simulating a WhatsApp message
    message_data = {
        "From": "whatsapp:+15558675309",
        "Body": "My child has a high fever and a rash"
    }
    
    try:
        print(f"   - Sending POST request to: {url}")
        print(f"   - With data: {message_data}")
        
        response = requests.post(url, data=message_data, timeout=60) # Increased timeout for model loading
        
        print("\n--- ✅ Backend responded ---")
        print(f"   - Status Code: {response.status_code}")
        
        # The webhook should return a simple "OK" 200 response.
        # The real test is to check the logs in the Flask server terminal.
        if response.status_code == 200:
            print("\n--- ✅ SUCCESS: The backend is running and responded correctly. ---")
            print("\n--- 👉 NOW, CHECK THE FLASK SERVER TERMINAL! ---")
            print("   Look for log lines like 'Raw model output:' to see the prediction.")
        else:
            print(f"\n--- 🔴 FAILURE: The backend returned an error. ---")
            print(f"   - Response Text: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("\n--- 🔴 FATAL ERROR ---")
        print("   Could not connect to the server. Is your Flask application running?")
        print("   Please run `python src/Backend/FlaskAPI/flasky.py` in another terminal.")
    except Exception as e:
        print(f"\n--- 🔴 An unexpected error occurred: {e} ---")

if __name__ == "__main__":
    test_webhook() 