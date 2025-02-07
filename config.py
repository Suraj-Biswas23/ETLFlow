import os

# MySQL Database Configuration
DB_USERNAME = "root"       # Change if needed
DB_PASSWORD = "password"   # Change if needed
DB_HOST = "localhost"
DB_NAME = "etlflow"

SQLALCHEMY_DATABASE_URI = f"mysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
