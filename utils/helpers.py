"""Small shared helpers: settings access, formatting, UI styling."""
import os
from datetime import datetime
from decimal import Decimal

import config
from database.connection import get_session
from database.models import BusinessSetting

DEFAULT_SETTINGS = {
    "business_name": "Bapasitaram Auto Parts",
    "business_address": "Shop address, City, State - PIN (edit in Settings)",
    "business_phone": "+91 00000 00000",
    "business_email": "",
    "gstin": "",
    "logo_path": config.DEFAULT_LOGO,
    "invoice_footer": "Thank you for shopping with us! Visit again.",
}


def get_settings() -> dict:
    data = dict(DEFAULT_SETTINGS)
    with get_session() as s:
        for row in s.query(BusinessSetting).all():
            if row.value is not None:
                data[row.key] = row.value
    return data


def save_settings(values: dict):
    with get_session() as s:
        for key, val in values.items():
            row = s.query(BusinessSetting).filter_by(key=key).first()
            if row:
                row.value = val
            else:
                s.add(BusinessSetting(key=key, value=val))


def fmt_money(value) -> str:
    return f"{config.CURRENCY} {Decimal(str(value or 0)):,.2f}"


def fmt_dt(value) -> str:
    return value.strftime("%d-%b-%Y %H:%M") if isinstance(value, datetime) else str(value or "")


def describe_part(name: str, bike: str = "") -> str:
    """Bill description: part name followed by the bike it fits."""
    return f"{name} - {bike}" if bike else name


def generate_logo(path: str, text: str = "RB"):
    """Create a simple placeholder logo if none exists."""
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (240, 240), "#1f4e79")
    d = ImageDraw.Draw(img)
    d.ellipse((20, 20, 220, 220), fill="#ffffff")
    d.ellipse((40, 40, 200, 200), fill="#1f4e79")
    d.text((92, 108), text, fill="#ffffff")
    img.save(path)


CUSTOM_CSS = """
<style>
:root { --primary:#1f4e79; --accent:#2e86c1; --bg:#f4f6f9; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1300px; }
h1, h2, h3 { color: #1f2d3d; font-family: 'Segoe UI', sans-serif; font-weight: 600; }
[data-testid="stSidebar"] { background: #1f2d3d; }
[data-testid="stSidebar"] * { color: #e8eef5 !important; }
.kpi { background:#fff; border:1px solid #e1e6ed; border-left:4px solid var(--primary);
       border-radius:8px; padding:14px 16px; box-shadow:0 1px 2px rgba(0,0,0,.04); }
.kpi .label { font-size:.78rem; color:#6b7a8c; text-transform:uppercase; letter-spacing:.04em; }
.kpi .value { font-size:1.6rem; font-weight:700; color:#1f2d3d; margin-top:2px; }
.totals-box { background:#fff; border:1px solid #e1e6ed; border-radius:8px; padding:14px 18px; }
.totals-box .row { display:flex; justify-content:space-between; padding:3px 0; }
.totals-box .grand { border-top:2px solid var(--primary); margin-top:6px; padding-top:8px;
                     font-size:1.25rem; font-weight:700; color:var(--primary); }
.bill-head { text-align:center; border-bottom:3px solid var(--primary); padding:6px 0 10px 0; margin-bottom:14px; }
.bill-head h1 { margin:0; padding:0; font-size:2.1rem; color:var(--primary); letter-spacing:.02em; }
.bill-head p { margin:2px 0 0 0; color:#4a5b6c; font-size:.9rem; }
.stButton>button, .stDownloadButton>button { border-radius:6px; font-weight:500; }
</style>
"""


def kpi(label: str, value: str) -> str:
    return f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div></div>'
