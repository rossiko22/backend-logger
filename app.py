from flask import Flask, request
from flask_restx import Api, Resource, fields
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dotenv import load_dotenv
import os

# Load .env locally (Render ignores this and uses real env vars)
load_dotenv()

app = Flask(__name__)
api = Api(app, version="1.1", title="API Stats Service",
          description="Track API usage stats with RESTful endpoints")

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Database connection function
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("Database connection error:", e)
        return None

# Swagger model for POST request
post_model = api.model('PostRequest', {
    'calledService': fields.String(required=True, description='Endpoint called remotely')
})

# --- Utility functions ---
def log_call(endpoint, method, ip, request_body=None, status_code=200):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO api_calls (endpoint, method, ip_address, request_body, status_code, called_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (endpoint, method, ip, request_body, status_code, datetime.now()))
            conn.commit()
        return True
    except Exception as e:
        print("Error logging call:", e)
        return False
    finally:
        conn.close()

def get_last_called():
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT endpoint, method, ip_address, called_at
                FROM api_calls
                ORDER BY called_at DESC
                LIMIT 1
            """)
            return cur.fetchone()
    except Exception as e:
        print("Error fetching last called:", e)
        return None
    finally:
        conn.close()

def get_most_frequent():
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT endpoint, COUNT(*) as count
                FROM api_calls
                GROUP BY endpoint
                ORDER BY count DESC
                LIMIT 1
            """)
            return cur.fetchone()
    except Exception as e:
        print("Error fetching most frequent:", e)
        return None
    finally:
        conn.close()

def get_counts():
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT endpoint, COUNT(*) as count
                FROM api_calls
                GROUP BY endpoint
            """)
            return cur.fetchall()
    except Exception as e:
        print("Error fetching counts:", e)
        return None
    finally:
        conn.close()

# --- POST endpoint ---
@api.route('/track')
class Track(Resource):
    @api.expect(post_model)
    def post(self):
        """Log a remote call (POST body: {calledService: /endpoint})"""
        data = request.json or {}
        endpoint_called = data.get('calledService')
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)

        success = log_call(endpoint=endpoint_called, method="POST", ip=ip, request_body=data)
        if success:
            return {"message": f"Logged call to {endpoint_called}", "ip": ip}, 201
        else:
            return {"error": "Failed to log call"}, 500

# --- GET endpoints ---
@api.route('/stats/last')
class LastCalled(Resource):
    def get(self):
        last = get_last_called()
        if last:
            return {"last_called": last}, 200
        else:
            return {"error": "Unable to fetch last called endpoint"}, 500

@api.route('/stats/most')
class MostFrequent(Resource):
    def get(self):
        most = get_most_frequent()
        if most:
            return {"most_frequent": most}, 200
        else:
            return {"error": "Unable to fetch most frequent endpoint"}, 500

@api.route('/stats/counts')
class Counts(Resource):
    def get(self):
        counts = get_counts()
        if counts:
            return {"counts": counts}, 200
        else:
            return {"error": "Unable to fetch endpoint counts"}, 500

# --- Optional: log all incoming requests automatically ---
@app.before_request
def log_every_request():
    if request.endpoint not in ['lastcalled', 'mostfrequent', 'counts', 'track']:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        log_call(
            endpoint=request.path,
            method=request.method,
            ip=ip,
            request_body=request.json if request.is_json else None
        )

# --- Run ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
