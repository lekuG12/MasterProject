from flask import Flask, request, jsonify

from 


app = Flask(__name__)

@app.route('/', methods=['GET'])
def user_input():
    return jsonify({
        'message': 'Your assistant is up and running!'
    })


@app.route('/webhook', methods=['POST'])
def sendMessage():
    data = request.get_json()
    to_number = data.get('to_number')
    body_text = data.get('body_text')

    # Here you would call your Twilio function to send the message
    # For example:




if __name__ == '__main__':
    app.run(debug=True)