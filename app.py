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
CORS(app, origins=[
    "http://localhost:4201",
    "http://localhost:5173",
    "*"
])

api = Api(
    app,
    version="1.2",
    title="API Stats Service",
    description="A comprehensive API for tracking and analyzing API usage statistics with PostgreSQL backend",
    doc="/docs",
)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# ==================== Database ====================

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print("Database connection error:", e)
        return None

# ==================== Namespaces ====================

ns_track = Namespace('track', description='Track API calls')
ns_stats = Namespace('stats', description='API usage statistics')
ns_health = Namespace('health', description='Health check endpoints')

api.add_namespace(ns_track, path='/track')
api.add_namespace(ns_stats, path='/stats')
api.add_namespace(ns_health, path='/health')

# ==================== Swagger Models ====================

track_request_model = api.model('TrackRequest', {
    'id': fields.Integer(required=True, description='External service ID'),
    'calledService': fields.String(required=True, description='Endpoint that was called remotely')
})

track_response_model = api.model('TrackResponse', {
    'message': fields.String,
    'ip': fields.String
})

call_info_model = api.model('CallInfo', {
    'endpoint': fields.String,
    'method': fields.String,
    'ip_address': fields.String,
    'called_at': fields.DateTime
})

last_called_response_model = api.model('LastCalledResponse', {
    'last_called': fields.Nested(call_info_model)
})

frequency_info_model = api.model('FrequencyInfo', {
    'endpoint': fields.String,
    'count': fields.Integer
})

most_frequent_response_model = api.model('MostFrequentResponse', {
    'most_frequent': fields.Nested(frequency_info_model)
})

counts_response_model = api.model('CountsResponse', {
    'counts': fields.List(fields.Nested(frequency_info_model))
})

health_response_model = api.model('HealthResponse', {
    'status': fields.String,
    'database': fields.String,
    'timestamp': fields.DateTime
})

# ==================== Utility Functions ====================

def log_call(external_user_id, endpoint, method, ip, request_body=None, status_code=200):
    if not endpoint:
        return False

    conn = get_db_connection()
    if not conn:
        return False

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
                Json(request_body) if request_body is not None else None,
                status_code,
                datetime.now()
            ))
            conn.commit()
        return True
    except Exception as e:
        print("Error logging call:", e)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
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
                ORDER BY count DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

def check_database_health():
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    finally:
        conn.close()

# ==================== Endpoints ====================

@ns_track.route('/')
class Track(Resource):
    @ns_track.expect(track_request_model, validate=True)
    @ns_track.marshal_with(track_response_model, code=201)
    def post(self):
        data = request.json or {}
        external_user_id = data.get('id')
        endpoint_called = data.get('calledService')
        raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        ip = raw_ip.split(',')[0].strip()

        success = log_call(
            external_user_id=external_user_id,
            endpoint=endpoint_called,
            method="POST",
            ip=ip,
            request_body=data
        )

        if success:
            return {"message": f"Logged call to {endpoint_called}", "ip": ip}, 201
        else:
            ns_track.abort(500, 'Failed to log call to database')

@ns_stats.route('/last')
class LastCalled(Resource):
    def get(self):
        last = get_last_called()
        if last:
            return {"last_called": last}, 200
        else:
            ns_stats.abort(500, 'Unable to fetch last called endpoint')

@ns_stats.route('/most')
class MostFrequent(Resource):
    def get(self):
        most = get_most_frequent()
        if most:
            return {"most_frequent": most}, 200
        else:
            ns_stats.abort(500, 'Unable to fetch most frequent endpoint')

@ns_stats.route('/counts')
class Counts(Resource):
    def get(self):
        counts = get_counts()
        if counts:
            return {"counts": counts}, 200
        else:
            ns_stats.abort(500, 'Unable to fetch counts')

@ns_health.route('/')
class Health(Resource):
    def get(self):
        db_healthy = check_database_health()
        if db_healthy:
            return {
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.now()
            }, 200
        else:
            ns_health.abort(503, 'Database connection failed')

# ==================== Middleware ====================

@app.before_request
def log_every_request():
    excluded = ['stats_last_called', 'stats_most_frequent', 'stats_counts', 'track_track', 'health_health']
    if request.endpoint and request.endpoint not in excluded:
        raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        ip = raw_ip.split(',')[0].strip()

        log_call(
            external_user_id=None,
            endpoint=request.path,
            method=request.method,
            ip=ip,
            request_body=request.json if request.is_json else None
        )

# ==================== Run ====================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
