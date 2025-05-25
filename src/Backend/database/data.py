from flask import Flask
from flask_sqlalchemy import SQLAlchemy as sql

from datetime import datetime
import logging


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interactions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = sql(app)
logger = logging.getLogger(__name__)


class Conversation(db.Model):
    __tablename__ = 'conversation'

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_input = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    response_time = db.Column(db.Float, nullable=True)  # Response generation time in seconds
    status = db.Column(db.String(20), default='sent', nullable=False)

    def __repr__(self):
        return f'<Conversation {self.id}: {self.phone_number}>'
    

    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'timestamp': self.timestamp.isoformat(),
            'user_input': self.user_input,
            'bot_response': self.bot_response,
            'response_time': self.response_time,
            'status': self.status
        }
    

def init_database(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {str(e)}")
            raise


def save_conversation(phone_number, user_input, bot_response, response_time=None, status='sent'):
    """Save conversation to database"""
    try:
        conversation = Conversation(
            phone_number=phone_number,
            user_input=user_input,
            bot_response=bot_response,
            response_time=response_time,
            status=status
        )
        
        db.session.add(conversation)
        db.session.commit()
        logger.info(f"Conversation saved for {phone_number}")
        return conversation
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        db.session.rollback()
        raise


def get_conversation_history(phone_number, limit=10):
    """Get recent conversation history for context"""
    try:
        conversations = Conversation.query.filter_by(
            phone_number=phone_number
        ).order_by(Conversation.timestamp.desc()).limit(limit).all()
        
        return [conv.to_dict() for conv in conversations]
    except Exception as e:
        logger.error(f"Error fetching conversation history: {str(e)}")
        return []
