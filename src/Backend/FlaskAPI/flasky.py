from flask import Flask, request, jsonify

from twilioM.nurseTalk import sendMessage


app = Flask(__name__)

@app.route('/', methods=['GET'])
def user_input():
    return jsonify({
        'message': 'Your assistant is up and running!'
    })


@app.route('/webhook', methods=['POST'])
def send_message():
    data = request.get_json()
    to_number = data.get('to_number')
    body_text = data.get('body_text')

    # Here you would call your Twilio function to send the message
    # For example:
    try:
        sendMessage(to_number, body_text)
        return jsonify({'status': 'success', 'message': 'Message sent successfully!'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/webhook', methods=['GET'])
def get_message():
    # This is a placeholder for the GET request
    # You can implement your logic here
    return jsonify({'status': 'success', 'message': 'GET request received!'}), 200




if __name__ == '__main__':
    app.run(debug=True)