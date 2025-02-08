from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
import logging
from dotenv import load_dotenv
from sqlalchemy import text, Table, Column, Integer, String, Float, Boolean, Date, DateTime, Time, MetaData, JSON
from sqlalchemy.exc import SQLAlchemyError
from extensions import db

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

# Load configuration from .env
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "fallback_default_key")
app.config['UPLOAD_FOLDER'] = os.getenv("UPLOAD_FOLDER", "data/")
app.config['ALLOWED_EXTENSIONS'] = set(os.getenv("ALLOWED_EXTENSIONS", "csv").split(","))

# Database Configuration
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_data(filepath):
    """Read the CSV file and return a DataFrame"""
    try:
        df = pd.read_csv(filepath)
        return df
    except Exception as e:
        logging.error(f"Error reading CSV: {e}")
        return None

def transform_data(df):
    """Clean and transform the data"""
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]  # Standardize column names
    df.dropna(inplace=True)  # Remove missing values
    return df

def infer_sqlalchemy_type(series):
    """Infer the best SQLAlchemy column type based on the data"""
    try:
        if pd.api.types.is_integer_dtype(series):
            return Integer
        elif pd.api.types.is_float_dtype(series):
            return Float
        elif pd.api.types.is_bool_dtype(series):
            return Boolean
        elif pd.api.types.is_datetime64_any_dtype(series):
            return DateTime
        elif pd.api.types.is_timedelta64_dtype(series):
            return Time
        elif pd.api.types.is_object_dtype(series):
            sample_value = series.dropna().iloc[0] if not series.dropna().empty else ""
            if isinstance(sample_value, str):
                if sample_value.startswith("{") and sample_value.endswith("}"):
                    return JSON
                return String(255)
        return String(255)
    except Exception as e:
        logging.error(f"Error inferring data type: {e}")
        return String(255)

def create_dynamic_table(df):
    """Dynamically create table schema based on CSV file"""
    metadata = MetaData()
    columns = [Column("id", Integer, primary_key=True, autoincrement=True)]
    
    for column in df.columns:
        col_type = infer_sqlalchemy_type(df[column])
        columns.append(Column(column, col_type))
    
    table = Table("etl_data", metadata, *columns)
    
    try:
        with db.engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS etl_data"))
            metadata.create_all(conn)
        logging.info("Table 'etl_data' created dynamically.")
    except SQLAlchemyError as e:
        logging.error(f"Error creating table: {e}")

def load_data(df):
    """Insert the transformed data into MySQL"""
    try:
        with app.app_context():
            create_dynamic_table(df)
            df.to_sql("etl_data", con=db.engine, if_exists="append", index=False)
            logging.info(f"{len(df)} records inserted into database.")
    except SQLAlchemyError as e:
        logging.error(f"Error inserting data: {e}")

@app.route("/", methods=["GET", "POST"])
def upload_file():
    records = []  # Default empty list for table
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            df = extract_data(filepath)
            if df is not None:
                df = transform_data(df)
                load_data(df)
                flash(f"File '{filename}' uploaded! {len(df)} rows inserted into database.", "success")

            return redirect(url_for("upload_file"))

    # Fetch data safely
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM etl_data LIMIT 10"))
            records = [dict(zip(result.keys(), row)) for row in result]  
    except SQLAlchemyError as e:
        logging.error(f"Error fetching data: {e}")

    return render_template("index.html", records=records)

@app.route("/api/data")
def get_data():
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM etl_data"))
            records = [dict(row) for row in result]
        return jsonify(records)
    except SQLAlchemyError as e:
        logging.error(f"Error fetching data: {e}")
        return jsonify({"error": "Error fetching data."}), 500
    
@app.route("/query", methods=["POST"])
def query_database():
    data = request.json
    query = data.get("query")

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        with db.engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            columns = result.keys()

            # Convert each row to a dictionary
            records = [dict(zip(columns, row)) for row in rows]

        return jsonify(records)

    except SQLAlchemyError as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/export/csv")
def export_csv():
    df = pd.read_sql("SELECT * FROM etl_data", db.engine)
    csv_path = "exported_data.csv"
    df.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)

@app.route("/export/parquet")
def export_parquet():
    df = pd.read_sql("SELECT * FROM etl_data", db.engine)
    parquet_path = "exported_data.parquet"
    df.to_parquet(parquet_path, engine="pyarrow", index=False)
    return send_file(parquet_path, as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
