from flask_sqlalchemy import SQLAlchemy
from app import app

app.config.from_object("config")

db = SQLAlchemy(app)

class DataRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    column1 = db.Column(db.String(255))
    column2 = db.Column(db.String(255))
    column3 = db.Column(db.Float)

db.create_all()
