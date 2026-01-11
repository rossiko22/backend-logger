"""
API Stats Service - A Flask RESTful API for tracking and analyzing API usage statistics

This application provides endpoints to:
- Track API calls with metadata (endpoint, method, IP address, request body)
- Retrieve statistics about API usage (last called, most frequent, counts)
- Health check for service and database connectivity

Features:
- Comprehensive Swagger/OpenAPI documentation at /docs
- PostgreSQL database backend for persistent storage
- Automatic request logging middleware
- Organized API namespaces (track, stats, health)
- Proper error handling and validation

Environment Variables:
- DATABASE_URL: PostgreSQL connection string (required)
- PORT: Server port (default: 5000)
- FLASK_DEBUG: Enable debug mode (default: False)

Author: Your Team
License: MIT
Version: 1.2
"""

from flask import Flask, request
from flask_restx import Api, Resource, fields, Namespace
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dotenv import load_dotenv
import os

# Load .env locally (Render ignores this and uses real env vars)
load_dotenv()

app = Flask(__name__)
api = Api(
    app,
    version="1.2",
    title="API Stats Service",
    description="A comprehensive API for tracking and analyzing API usage statistics with PostgreSQL backend",
    doc="/docs",
    contact="Your Team",
    license="MIT"
)

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

# ==================== Namespaces ====================
ns_track = Namespace('track', description='Track API calls')
ns_stats = Namespace('stats', description='API usage statistics')
ns_health = Namespace('health', description='Health check endpoints')

api.add_namespace(ns_track, path='/track')
api.add_namespace(ns_stats, path='/stats')
api.add_namespace(ns_health, path='/health')

# ==================== Swagger Models ====================

# Request Models
track_request_model = api.model('TrackRequest', {
    'calledService': fields.String(
        required=True,
        description='The endpoint that was called remotely',
        example='/api/users'
    )
})

# Response Models
track_response_model = api.model('TrackResponse', {
    'message': fields.String(description='Success message', example='Logged call to /api/users'),
    'ip': fields.String(description='IP address of the caller', example='192.168.1.1')
})

call_info_model = api.model('CallInfo', {
    'endpoint': fields.String(description='API endpoint', example='/api/users'),
    'method': fields.String(description='HTTP method', example='GET'),
    'ip_address': fields.String(description='IP address', example='192.168.1.1'),
    'called_at': fields.DateTime(description='Timestamp of the call', example='2024-01-11T12:00:00')
})

last_called_response_model = api.model('LastCalledResponse', {
    'last_called': fields.Nested(call_info_model, description='Last called endpoint information')
})

frequency_info_model = api.model('FrequencyInfo', {
    'endpoint': fields.String(description='API endpoint', example='/api/users'),
    'count': fields.Integer(description='Number of times called', example=42)
})

most_frequent_response_model = api.model('MostFrequentResponse', {
    'most_frequent': fields.Nested(frequency_info_model, description='Most frequently called endpoint')
})

counts_response_model = api.model('CountsResponse', {
    'counts': fields.List(fields.Nested(frequency_info_model), description='Call counts for all endpoints')
})

error_model = api.model('Error', {
    'error': fields.String(description='Error message', example='Unable to connect to database')
})

health_response_model = api.model('HealthResponse', {
    'status': fields.String(description='Service status', example='healthy'),
    'database': fields.String(description='Database connection status', example='connected'),
    'timestamp': fields.DateTime(description='Current server timestamp')
})

# ==================== Utility Functions ====================

def log_call(endpoint, method, ip, request_body=None, status_code=200):
    """Log an API call to the database"""
    if not endpoint:
        print("Warning: endpoint is None or empty")
        return False

    conn = get_db_connection()
    if not conn:
        print("Error: Unable to establish database connection")
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
        print(f"Error logging call: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_last_called():
    """Retrieve the last called API endpoint from the database"""
    conn = get_db_connection()
    if not conn:
        print("Error: Unable to establish database connection")
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
        print(f"Error fetching last called: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_most_frequent():
    """Retrieve the most frequently called API endpoint"""
    conn = get_db_connection()
    if not conn:
        print("Error: Unable to establish database connection")
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
        print(f"Error fetching most frequent: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_counts():
    """Retrieve call counts for all API endpoints"""
    conn = get_db_connection()
    if not conn:
        print("Error: Unable to establish database connection")
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
    except Exception as e:
        print(f"Error fetching counts: {e}")
        return None
    finally:
        if conn:
            conn.close()


def check_database_health():
    """Check if database connection is healthy"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ==================== Endpoints ====================

@ns_track.route('/')
class Track(Resource):
    @ns_track.doc(
        'track_api_call',
        description='Track and log an API call to the database',
        responses={
            201: ('Success', track_response_model),
            400: ('Validation Error', error_model),
            500: ('Server Error', error_model)
        }
    )
    @ns_track.expect(track_request_model, validate=True)
    @ns_track.marshal_with(track_response_model, code=201)
    def post(self):
        """Track an API call"""
        data = request.json or {}
        endpoint_called = data.get('calledService')

        if not endpoint_called:
            ns_track.abort(400, 'calledService field is required')

        ip = request.headers.get('X-Forwarded-For', request.remote_addr)

        success = log_call(endpoint=endpoint_called, method="POST", ip=ip, request_body=data)
        if success:
            return {"message": f"Logged call to {endpoint_called}", "ip": ip}, 201
        else:
            ns_track.abort(500, 'Failed to log call to database')

@ns_stats.route('/last')
class LastCalled(Resource):
    @ns_stats.doc(
        'get_last_called',
        description='Retrieve information about the most recently called API endpoint',
        responses={
            200: ('Success', last_called_response_model),
            500: ('Server Error', error_model)
        }
    )
    @ns_stats.marshal_with(last_called_response_model, code=200)
    def get(self):
        """Get the last called API endpoint"""
        last = get_last_called()
        if last:
            return {"last_called": last}, 200
        else:
            ns_stats.abort(500, 'Unable to fetch last called endpoint from database')


@ns_stats.route('/most')
class MostFrequent(Resource):
    @ns_stats.doc(
        'get_most_frequent',
        description='Retrieve the most frequently called API endpoint with call count',
        responses={
            200: ('Success', most_frequent_response_model),
            500: ('Server Error', error_model)
        }
    )
    @ns_stats.marshal_with(most_frequent_response_model, code=200)
    def get(self):
        """Get the most frequently called endpoint"""
        most = get_most_frequent()
        if most:
            return {"most_frequent": most}, 200
        else:
            ns_stats.abort(500, 'Unable to fetch most frequent endpoint from database')


@ns_stats.route('/counts')
class Counts(Resource):
    @ns_stats.doc(
        'get_all_counts',
        description='Retrieve call counts for all API endpoints, showing usage statistics',
        responses={
            200: ('Success', counts_response_model),
            500: ('Server Error', error_model)
        }
    )
    @ns_stats.marshal_with(counts_response_model, code=200)
    def get(self):
        """Get call counts for all endpoints"""
        counts = get_counts()
        if counts:
            return {"counts": counts}, 200
        else:
            ns_stats.abort(500, 'Unable to fetch endpoint counts from database')


@ns_health.route('/')
class Health(Resource):
    @ns_health.doc(
        'health_check',
        description='Check the health status of the API service and database connection',
        responses={
            200: ('Healthy', health_response_model),
            503: ('Unhealthy', error_model)
        }
    )
    @ns_health.marshal_with(health_response_model, code=200)
    def get(self):
        """Health check endpoint"""
        db_healthy = check_database_health()

        if db_healthy:
            return {
                'status': 'healthy',
                'database': 'connected',
                'timestamp': datetime.now()
            }, 200
        else:
            ns_health.abort(503, 'Database connection failed')

# ==================== Request Logging Middleware ====================
@app.before_request
def log_every_request():
    """Automatically log all incoming requests (except stats/health endpoints)"""
    # Skip logging for stats, health, and Swagger documentation endpoints
    excluded_endpoints = [
        'stats_last_called', 'stats_most_frequent', 'stats_counts',
        'track_track', 'health_health', 'doc', 'specs', 'static'
    ]

    if request.endpoint and request.endpoint not in excluded_endpoints:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        log_call(
            endpoint=request.path,
            method=request.method,
            ip=ip,
            request_body=request.json if request.is_json else None
        )

# ==================== Application Entry Point ====================
if __name__ == "__main__":
    # Get configuration from environment variables
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    port = int(os.environ.get("PORT", 5000))

    print(f"Starting API Stats Service on port {port}")
    print(f"Debug mode: {debug_mode}")
    print(f"Swagger documentation available at: http://0.0.0.0:{port}/docs")

    app.run(host="0.0.0.0", port=port, debug=debug_mode)
