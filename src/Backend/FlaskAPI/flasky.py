from flask import Flask, request, jsonify
import re
import logging
from datetime import datetime
import time

from Backend.database.data import db, init_database, save_conversation, get_conversation_history
from Backend.Model.loadModel import initialize_model, get_ai_response
from twilioM.nurseTalk import send_message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nurse_talk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False





@app.route('/webhook', methods=['POST'])
def send_message():

    start_time = time.time()

    try:
        data = request.get_json()
        if not data:
            logger.warning("Webhook received empty data")
            return jsonify({
                'status': 'error', 
                'message': 'No data provided'
            }), 400

        to_number = data.get('to_number', '').strip()
        user_input = data.get('body_text', '').strip()
        message_type = data.get('message_type', 'whatsapp')  # whatsapp or sms

        if not to_number or not user_input:
            return jsonify({
                'status': 'error', 
                'message': 'Missing required fields: to_number and body_text'
            }), 400
        

        if len(user_input) > 1600:
            return jsonify({
                'status': 'error', 
                'message': 'Message too long (max 1600 characters)'
            }), 400

        # Get conversation history for context
        conversation_history = get_conversation_history(to_number, limit=5)

        try:
            bot_response, response_time = get_ai_response(user_input, conversation_history)
        except Exception as ai_error:
            logger.error(f"AI model error: {str(ai_error)}")
            bot_response = "I apologize, but I'm having technical difficulties. A healthcare professional will contact you shortly."
            response_time = 0


        try:
            message_result = send_message(to_number, bot_response, message_type)
            logger.info(f"Message sent successfully to {to_number}")
        except Exception as sms_error:
            logger.error(f"Failed to send message to {to_number}: {str(sms_error)}")
            
            # Save conversation even if sending fails
            try:
                save_conversation(to_number, user_input, bot_response, response_time, 'failed')
            except:
                pass
                
            return jsonify({
                'status': 'error', 
                'message': f'Failed to send message: {str(sms_error)}'
            }), 500
        

        try:
            save_conversation(to_number, user_input, bot_response, response_time, 'sent')
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            # Continue since message was sent successfully

        total_time = time.time() - start_time
        logger.info(f"Webhook processed in {total_time:.2f}s")

        return jsonify({
            'status': 'success', 
            'message': 'Message sent successfully',
            'bot_response': bot_response,
            'phone_number': to_number,
            'response_time': response_time,
            'total_time': total_time
        }), 200
    
    except Exception as e:
        logger.error(f"Unexpected error in webhook: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': 'Internal server error'
        }), 500
    


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'ai_model': 'loaded' if hasattr(get_ai_response, '__self__') else 'not_loaded',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/conversations/<phone_number>', methods=['GET'])
def get_conversations(phone_number):
    """Get conversation history for a phone number"""
    try:
        limit = request.args.get('limit', 50, type=int)
        conversations = get_conversation_history(phone_number, limit)

        return jsonify({
            'status': 'success',
            'phone_number': phone_number,
            'conversations': conversations,
            'count': len(conversations)
        }), 200

    except Exception as e:
        logger.error(f"Error fetching conversations: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch conversations'
        }), 500

def initialize_app():
    """Initialize the Flask application and its components"""
    try:
        # Initialize database
        init_database(app)
        logger.info("Database initialized")
        
        # Initialize AI model
        initialize_model()
        logger.info("AI model initialized")
        
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

if __name__ == '__main__':
    # Initialize all components
    initialize_app()
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)