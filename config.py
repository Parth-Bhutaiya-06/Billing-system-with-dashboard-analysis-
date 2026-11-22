"""Application configuration."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("BILLING_DB_PATH", os.path.join(BASE_DIR, "billing.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DEFAULT_LOGO = os.path.join(ASSETS_DIR, "logo.png")

APP_TITLE = "Bapasitaram Auto Parts"
CURRENCY = "Rs."
PAYMENT_METHODS = ["Cash", "UPI", "Card", "Other"]
INVOICE_PREFIX = "INV"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
