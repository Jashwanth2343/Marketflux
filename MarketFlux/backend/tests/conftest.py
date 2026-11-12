"""Dummy env so importing the API in CI does not require real secrets.

Values already present in the environment are left alone. load_dotenv() inside
server.py does not override variables that are already set.
"""
import os

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "marketflux_test")
os.environ.setdefault("JWT_SECRET", "ci-jwt-secret-must-be-at-least-32-characters")
os.environ.setdefault("MARKETFLUX_ENV", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ENABLE_CODE_SANDBOX", "false")
os.environ.setdefault("DEMO_MODE", "false")
