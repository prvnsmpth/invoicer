import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
INVOICES_DIR = BASE_DIR / "invoices"
DATABASE_PATH = BASE_DIR / "invoicer.db"

CREDENTIALS_DIR.mkdir(exist_ok=True)
INVOICES_DIR.mkdir(exist_ok=True)

GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE = CREDENTIALS_DIR / "token.json"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"

DEFAULT_CURRENCY = "INR"
DEFAULT_TIMEZONE = "Asia/Kolkata"