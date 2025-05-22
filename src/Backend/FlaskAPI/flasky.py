from flask import Flask, request, jsonify


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

    


if __name__ == '__main__':
    app.run(debug=True)