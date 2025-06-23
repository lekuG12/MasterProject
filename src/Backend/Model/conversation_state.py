from datetime import datetime, timedelta
from enum import Enum, auto
import logging

logger = logging.getLogger(__name__)
class ConversationStateType(Enum):
    """Represents the different states of a user conversation."""
    GREETING = auto()               # The start of a new, fresh conversation.
    COLLECTING_SYMPTOMS = auto()    # The system is actively asking for and recording symptoms.

class ConversationState:
    """Holds all information about a single user's ongoing session."""
    def __init__(self):
        self.type = ConversationStateType.GREETING
        self.symptom_history = []
        self.last_update = datetime.now()

    def add_symptom(self, symptom: str):
        """Adds a new symptom to the session's history."""
        self.symptom_history.append(symptom)
        self.last_update = datetime.now()
    
    def get_all_symptoms(self) -> str:
        """Returns a single string of all recorded symptoms."""
        return ". ".join(self.symptom_history)

    def reset(self):
        """Resets the conversation to its initial state."""
        self.type = ConversationStateType.GREETING
        self.symptom_history = []
        self.last_update = datetime.now()

# In-memory session store
_conversation_states = {}

def get_conversation_state(phone_number: str) -> ConversationState:
    """Gets, or creates, the conversation state for a given phone number."""
    if phone_number not in _conversation_states:
        _conversation_states[phone_number] = ConversationState()
    
    state = _conversation_states[phone_number]
    # Reset the conversation if it has been inactive for more than 30 minutes
    if datetime.now() - state.last_update > timedelta(minutes=30):
        state.reset()
        logger.info(f"Resetting stale conversation for {phone_number}")
        
    return state

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

def reset_conversation_questions(phone_number):
    """Reset the asked questions for a given phone number to start fresh"""
    if phone_number in _conversation_states:
        _conversation_states[phone_number]["state"].reset_questions()
        _conversation_states[phone_number]["last_update"] = datetime.now()
        return True
    return False