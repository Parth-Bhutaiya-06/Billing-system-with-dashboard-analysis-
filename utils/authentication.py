"""Password hashing (PBKDF2-SHA256, stdlib only) and user authentication."""
import hashlib
import hmac
import os

from database.connection import get_session
from database.models import User

ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def authenticate(username: str, password: str):
    """Return a plain dict for the user on success, else None."""
    with get_session() as s:
        user = s.query(User).filter(User.username == (username or "").strip()).first()
        if user and user.is_active and verify_password(password or "", user.password_hash):
            return {"id": user.id, "username": user.username,
                    "full_name": user.full_name, "role": user.role}
    return None


# Role-based permissions: which sidebar pages each role may open.
ROLE_PAGES = {
    "admin": ["Dashboard", "New Bill", "Products", "Inventory", "Customers",
              "Invoice History", "Reports", "Employees", "Settings"],
    "employee": ["Dashboard", "New Bill", "Products", "Inventory", "Customers",
                 "Invoice History"],
}


def allowed_pages(role: str):
    return ROLE_PAGES.get(role, ROLE_PAGES["employee"])


def is_admin(user) -> bool:
    return bool(user) and user.get("role") == "admin"
