from flask import Flask, request


app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def user_input():
    pass


if __name__ == '__main__':
    app.run(debug=True)



