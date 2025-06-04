from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Parse incoming message
    incoming_msg = request.form.get('Body', '').lower()
    sender_id = request.form.get('From')

    # Process message (e.g., echo response)
    resp = MessagingResponse()
    resp.message(f"You said: {incoming_msg}")
    
    return str(resp)

if __name__ == '__main__':
    app.run(port=5000)