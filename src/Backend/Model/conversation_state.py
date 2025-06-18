from datetime import datetime
from enum import Enum, auto

class ConversationStateType(Enum):
    GREETING = auto()
    ACTIVE = auto()
    WAITING = auto()
    ENDED = auto()

class ConversationState:
    def __init__(self):
        self.type = ConversationStateType.GREETING
        self.context = ""
        self.last_question = ""
        self.asked_questions = set()
        self.last_update = datetime.now()

# Dictionary to store conversation states for different phone numbers
_conversation_states = {}

def get_conversation_state(phone_number):
    """Get the conversation state for a given phone number"""
    if phone_number not in _conversation_states:
        _conversation_states[phone_number] = {
            "state": ConversationState(),
            "last_update": datetime.now()
        }
    return _conversation_states[phone_number]["state"]

def update_conversation_state(phone_number, state):
    """Update the conversation state for a given phone number"""
    _conversation_states[phone_number] = {
        "state": state,
        "last_update": datetime.now()
    }

def clear_conversation_state(phone_number):
    """Clear the conversation state for a given phone number"""
    if phone_number in _conversation_states:
        del _conversation_states[phone_number]