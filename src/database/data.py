from flask import Flask
from flask_sqlalchemy import SQLAlchemy as sql

from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interactions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = sql(app)


class conversation(db.Model):
    __tablename__ = 'conversation'

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_input = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)