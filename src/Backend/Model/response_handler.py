import re
import random

def clean_response(text):
    """Clean up the AI response by removing repetitive elements and tags"""
    # ...existing clean_response code from flasky.py...

def add_conversational_elements(response):
    """Add conversational elements to make responses more natural"""
    empathy_phrases = [
        "I understand this might be concerning. ",
        "I hear you, and I'm here to help. ",
        "Thank you for sharing that with me. ",
        "I can see why you're worried. "
    ]
    
    follow_ups = [
        "How are you feeling now?",
        "Is there anything else you'd like to know?",
        "Would you like me to explain anything in more detail?",
        "Do you have any other symptoms I should know about?"
    ]
    
    empathy = random.choice(empathy_phrases)
    follow_up = random.choice(follow_ups)
    return f"{empathy}{response}\n\n{follow_up}"