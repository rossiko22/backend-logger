"""
API Stats Service - A Flask RESTful API for tracking and analyzing API usage statistics
"""

from flask import Flask, request
from flask_restx import Api, Resource, fields, Namespace
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime
from dotenv import load_dotenv
import os

# Load .env locally (Render ignores this and uses real env vars)
load_dotenv()

app = Flask(__name__)

# Allow local frontends to call the cloud API
CORS(
    app,
    supports_credentials=True,
    origins=[
        "http://localhost:4201",
        "http://localhost:4200",
        "http://localhost:5173",
    ]
)

api = Api(
    app,
    version="1.2",
    title="API Stats Service",
    description="Track and analyze API usage statistics",
    doc="/docs",
)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# ==================== Database ====================

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# ==================== Namespaces ====================

ns_track = Namespace('track', description='Track API calls')
ns_stats = Namespace('stats', description='API usage statistics')
ns_health = Namespace('health', description='Health check')

api.add_namespace(ns_track, path='/track')
api.add_namespace(ns_stats, path='/stats')
api.add_namespace(ns_health, path='/health')

# ==================== Models ====================

track_request_model = api.model('TrackRequest', {
    'id': fields.Integer(required=True, description="External user/service ID"),
    'calledService': fields.String(required=True, description="Endpoint that was called")
})

# ==================== Helpers ====================

def log_call(external_user_id, endpoint, method, ip, request_body=None, status_code=200):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO api_calls (external_user_id, endpoint, method, ip_address, request_body, status_code, called_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                external_user_id,
                endpoint,
                method,
                ip,
                Json(request_body) if request_body else None,
                status_code,
                datetime.now()
            ))
            conn.commit()
        return True
    except Exception as e:
        print("Error logging call:", e)
        conn.rollback()
        return False
    finally:
        conn.close()

# ==================== Queries ====================

def get_last_called():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT external_user_id, endpoint, method, ip_address, called_at
                FROM api_calls
                ORDER BY called_at DESC
                LIMIT 1
            """)
            return cur.fetchone()
    finally:
        conn.close()

def get_most_frequent():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT endpoint, COUNT(*) AS total_calls
                FROM api_calls
                GROUP BY endpoint
                ORDER BY total_calls DESC
                LIMIT 1
            """)
            return cur.fetchone()
    finally:
        conn.close()

def get_counts():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT endpoint, COUNT(*) AS total_calls
                FROM api_calls
                GROUP BY endpoint
                ORDER BY total_calls DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

# ==================== Endpoints ====================

@ns_track.route('/')
class Track(Resource):
    @ns_track.expect(track_request_model, validate=True)
    def post(self):
        data = request.json
        raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        ip = raw_ip.split(',')[0].strip()

        success = log_call(
            external_user_id=data['id'],
            endpoint=data['calledService'],
            method="POST",
            ip=ip,
            request_body=data
        )

        if success:
            return {
                "message": "Logged successfully",
                "endpoint": data['calledService']
            }, 201

        return {"error": "Logging failed"}, 500


@ns_stats.route('/last')
class Last(Resource):
    def get(self):
        row = get_last_called()
        if not row:
            return {"message": "No data yet"}, 200

        return {
            "last_called": {
                "user_id": row["external_user_id"],
                "endpoint": row["endpoint"],
                "method": row["method"],
                "ip": row["ip_address"],
                "time": row["called_at"]
            }
        }


@ns_stats.route('/most')
class Most(Resource):
    def get(self):
        row = get_most_frequent()
        if not row:
            return {"message": "No data yet"}, 200

        return {
            "most_frequent": {
                "endpoint": row["endpoint"],
                "total_calls": row["total_calls"]
            }
        }


@ns_stats.route('/counts')
class Counts(Resource):
    def get(self):
        rows = get_counts()
        return {
            "counts": [
                {"endpoint": r["endpoint"], "total_calls": r["total_calls"]}
                for r in rows
            ]
        }


@ns_health.route('/')
class Health(Resource):
    def get(self):
        return {"status": "ok", "time": datetime.now()}


# ==================== Run ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
