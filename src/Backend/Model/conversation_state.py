from enum import Enum
from datetime import datetime

class ConversationState(Enum):
    GREETING = "greeting"
    COLLECTING_INFO = "collecting_info"
    PROVIDING_ADVICE = "providing_advice"
    FOLLOW_UP = "follow_up"
    FAREWELL = "farewell"

_conversation_states = {}

def get_conversation_state(phone_number):
    """Get the current conversation state for a phone number"""
    return _conversation_states.get(phone_number, {}).get("state", ConversationState.GREETING)

def update_conversation_state(phone_number, state):
    """Update the conversation state for a phone number"""
    if phone_number not in _conversation_states:
        _conversation_states[phone_number] = {}
    _conversation_states[phone_number].update({
        "state": state,
        "last_update": datetime.now()
    })