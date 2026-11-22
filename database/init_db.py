"""Create tables and seed default data (idempotent)."""
from sqlalchemy import inspect, text

from database.connection import get_engine, get_session
from database.models import (Base, Bike, BusinessSetting, Category, Customer, Product,
                             StockHistory, User)
import config
from utils.authentication import hash_password
from utils.helpers import DEFAULT_SETTINGS

SAMPLE_BIKES = ["Hero Splendor", "Honda Shine", "Bajaj Pulsar 150", "TVS Apache RTR 160",
                "Royal Enfield Classic 350"]

SAMPLE_CATEGORIES = ["Filters", "Brakes", "Engine", "Electrical", "Lubricants",
                     "Suspension", "Body Parts"]

# name, part no, category, bike, purchase, selling, gst, qty, min stock
SAMPLE_PRODUCTS = [
    ("Air Filter", "FLT-1001", "Filters", "Honda Shine", "120.00", "180.00", "18", 40, 10),
    ("Oil Filter", "FLT-1002", "Filters", "Hero Splendor", "70.00", "110.00", "18", 35, 10),
    ("Brake Pad Front", "BRK-2001", "Brakes", "Hero Splendor", "120.00", "190.00", "18", 40, 10),
    ("Brake Shoe Rear", "BRK-2002", "Brakes", "Hero Splendor", "90.00", "140.00", "18", 30, 10),
    ("Spark Plug", "ENG-3001", "Engine", "TVS Apache RTR 160", "90.00", "130.00", "18", 60, 15),
    ("Clutch Plate Set", "ENG-3002", "Engine", "Honda Shine", "300.00", "420.00", "18", 20, 5),
    ("Chain Sprocket Kit", "ENG-3003", "Engine", "Bajaj Pulsar 150", "650.00", "850.00", "18", 15, 5),
    ("Headlight Bulb 12V", "ELC-4001", "Electrical", "Bajaj Pulsar 150", "60.00", "100.00", "18", 50, 10),
    ("Battery 12V 5Ah", "ELC-4002", "Electrical", "Hero Splendor", "850.00", "1100.00", "28", 10, 3),
    ("Horn", "ELC-4003", "Electrical", "Royal Enfield Classic 350", "150.00", "240.00", "18", 3, 5),
    ("Engine Oil 1L", "LUB-5001", "Lubricants", None, "380.00", "480.00", "18", 80, 20),
    ("Chain Lube Spray", "LUB-5002", "Lubricants", None, "90.00", "140.00", "18", 8, 10),
    ("Rear Shock Absorber (Pair)", "SUS-6001", "Suspension", "TVS Apache RTR 160", "900.00", "1250.00", "18", 12, 4),
    ("Side Mirror (Pair)", "BDY-7001", "Body Parts", "Royal Enfield Classic 350", "350.00", "520.00", "18", 6, 5),
]


def _migrate(engine):
    """Add columns introduced after the first release to databases created earlier."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "bike_id" not in {c["name"] for c in insp.get_columns("products")}:
            conn.execute(text("ALTER TABLE products ADD COLUMN bike_id INTEGER REFERENCES bikes(id)"))
        if "bike_name" not in {c["name"] for c in insp.get_columns("invoice_items")}:
            conn.execute(text("ALTER TABLE invoice_items ADD COLUMN bike_name VARCHAR(100)"))


def init_db(seed: bool = True):
    engine = get_engine()
    Base.metadata.create_all(engine)
    _migrate(engine)
    if not seed:
        return
    with get_session() as s:
        if s.query(User).count() == 0:
            s.add(User(username=config.DEFAULT_ADMIN_USERNAME, full_name="Administrator",
                       password_hash=hash_password(config.DEFAULT_ADMIN_PASSWORD), role="admin"))
            s.add(User(username="cashier", full_name="Sample Cashier",
                       password_hash=hash_password("cashier123"), role="employee"))
        if s.query(Category).count() == 0:
            for name in SAMPLE_CATEGORIES:
                s.add(Category(name=name))
        if s.query(Bike).count() == 0:
            for name in SAMPLE_BIKES:
                s.add(Bike(name=name))
        s.flush()
        if s.query(Product).count() == 0:
            cats = {c.name: c.id for c in s.query(Category).all()}
            bikes = {b.name: b.id for b in s.query(Bike).all()}
            for name, sku, cat, bike, pp, sp, gst, qty, mn in SAMPLE_PRODUCTS:
                p = Product(name=name, sku=sku, category_id=cats[cat],
                            bike_id=bikes.get(bike) if bike else None, purchase_price=pp,
                            selling_price=sp, gst_percent=gst, quantity=qty, min_stock=mn)
                s.add(p)
                s.flush()
                s.add(StockHistory(product_id=p.id, change=qty, old_quantity=0,
                                   new_quantity=qty, reason="Opening stock", user_name="system"))
        if s.query(Customer).count() == 0:
            s.add(Customer(name="Rahul Sharma", phone="9876500001", email="rahul@example.com",
                           address="Navrangpura, Ahmedabad"))
            s.add(Customer(name="Priya Patel", phone="9876500002", email="priya@example.com",
                           address="Satellite, Ahmedabad"))
        for key, val in DEFAULT_SETTINGS.items():
            if not s.query(BusinessSetting).filter_by(key=key).first():
                s.add(BusinessSetting(key=key, value=val))
        # Databases created before the shop name was set still hold the old sample name.
        row = s.query(BusinessSetting).filter_by(key="business_name").first()
        if row and row.value == "Sample Retail Store":
            row.value = DEFAULT_SETTINGS["business_name"]


if __name__ == "__main__":
    init_db()
    print("Database initialised.")
