from flask import Flask, request, jsonify
import re
import logging
from datetime import datetime
from twilioM.nurseTalk import sendMessage
from Backend.database.data import db, conversation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nurse_talk.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db.init_app(app)

def generate_response(user_input, phone_number):
    lower_input = user_input.lower()

    


@app.route('/webhook', methods=['POST'])
def send_message():
    data = request.get_json()

    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided!'}), 400
    

    to_number = data.get('to_number')
    body_text = data.get('body_text')

    if not to_number or not body_text:
        return jsonify({'status': 'error', 'message': 'Missing required fields!'}), 400

    try:
        message = sendMessage(to_number, body_text)

        new_conversation  = conversation(
            phone_number=to_number,
            user_input='webhook_message'
            bot_response=body_text
        )

        db.session.add(new_conversation)
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Message sent successfully!'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)