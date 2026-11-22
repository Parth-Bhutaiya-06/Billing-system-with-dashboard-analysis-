from decimal import Decimal

import pytest

from pdf.invoice_generator import generate_invoice_pdf
from services import billing_service as bs, inventory_service as inv, invoice_service as invs
from services.inventory_service import ServiceError
from utils.authentication import authenticate, hash_password, verify_password
from utils.calculations import amount_in_words, calculate_invoice, calculate_line
from utils.helpers import get_settings


def test_line_and_invoice_math():
    c = calculate_line("95.00", 2, "19.00", "5")
    assert c["taxable"] == Decimal("171.00") and c["gst"] == Decimal("8.55")
    totals = calculate_invoice(
        [{"unit_price": "95.00", "quantity": 2, "gst_percent": "5"},
         {"unit_price": "20.00", "quantity": 3, "gst_percent": "12"}], "percent", 10)
    assert totals["subtotal"] == Decimal("250.00")
    assert totals["discount"] == Decimal("25.00")
    assert totals["gst"] == Decimal("15.03")
    assert totals["grand_total"] == Decimal("240.03")


def test_discount_cannot_exceed_subtotal():
    with pytest.raises(ValueError):
        calculate_invoice([{"unit_price": "10", "quantity": 1, "gst_percent": "0"}], "amount", 50)


def test_amount_in_words():
    assert amount_in_words("1234.50") == "Rupees One Thousand Two Hundred Thirty Four and Fifty Paise Only"
    assert amount_in_words("100000") == "Rupees One Lakh Only"


def test_password_hashing():
    h = hash_password("secret1")
    assert "secret1" not in h and verify_password("secret1", h) and not verify_password("nope", h)


def test_login(db):
    assert authenticate("admin", "admin123")["role"] == "admin"
    assert authenticate("admin", "wrong") is None


def test_invoice_reduces_stock_and_freezes_prices(db):
    pid = inv.search_products("FLT-1001")[0]["id"]
    before = inv.get_product(pid)["quantity"]
    iid = bs.create_invoice([{"product_id": pid, "quantity": 3}], customer_id=1,
                            payment_method="UPI", user={"id": 1, "full_name": "Administrator"})
    assert inv.get_product(pid)["quantity"] == before - 3
    snap = invs.get_invoice(iid)
    assert snap["items"][0]["unit_price"] == Decimal("180.00")
    assert snap["employee_name"] == "Administrator"

    # price change must not touch history
    p = inv.get_product(pid)
    inv.update_product(pid, p["name"], p["sku"], p["category"], "70", "999", "5", p["min_stock"])
    assert invs.get_invoice(iid)["items"][0]["unit_price"] == Decimal("180.00")
    assert invs.get_invoice(iid)["grand_total"] == snap["grand_total"]


def test_insufficient_stock_blocks_and_rolls_back(db):
    a = inv.search_products("FLT-1001")[0]
    b = inv.search_products("LUB-5002")[0]  # only 8 in stock
    qa, qb = a["quantity"], b["quantity"]
    with pytest.raises(ServiceError):
        bs.create_invoice([{"product_id": a["id"], "quantity": 1},
                           {"product_id": b["id"], "quantity": qb + 1}])
    assert inv.get_product(a["id"])["quantity"] == qa
    assert inv.get_product(b["id"])["quantity"] == qb
    assert invs.search_invoices() == []


def test_invoice_numbers_sequential(db):
    pid = inv.search_products("FLT-1001")[0]["id"]
    n1 = invs.get_invoice(bs.create_invoice([{"product_id": pid, "quantity": 1}]))["invoice_number"]
    n2 = invs.get_invoice(bs.create_invoice([{"product_id": pid, "quantity": 1}]))["invoice_number"]
    assert n1.endswith("0001") and n2.endswith("0002")


def test_bill_keeps_customer_and_bike_name(db):
    pid = inv.search_products("FLT-1001")[0]["id"]
    snap = invs.get_invoice(bs.create_invoice([{"product_id": pid, "quantity": 2}], walkin_name="Ramesh"))
    assert snap["customer_name"] == "Ramesh"
    assert snap["items"][0]["description"] == "Air Filter - Honda Shine"
    # renaming the bike afterwards must not change the saved bill
    bike = [b for b in inv.list_bikes() if b["name"] == "Honda Shine"][0]
    inv.rename_bike(bike["id"], "Honda Shine 125")
    assert invs.get_invoice(snap["id"])["items"][0]["description"] == "Air Filter - Honda Shine"


def test_pdfs_generate_both_formats(db):
    pid = inv.search_products("FLT-1001")[0]["id"]
    invoice = invs.get_invoice(bs.create_invoice([{"product_id": pid, "quantity": 2}],
                                                 discount_type="amount", discount_value=10))
    for fmt in ("A4", "80mm"):
        assert generate_invoice_pdf(invoice, get_settings(), fmt)[:4] == b"%PDF"


def test_dashboard_and_reports_use_db(db):
    from datetime import date
    pid = inv.search_products("FLT-1001")[0]["id"]
    bs.create_invoice([{"product_id": pid, "quantity": 2}], payment_method="Cash")
    stats = invs.dashboard_stats()
    assert stats["invoices_today"] == 1 and stats["sales_today"] > 0
    assert invs.sales_summary(date.today(), date.today())["invoices"] == 1
    assert invs.top_products().iloc[0]["Units Sold"] == 2
    assert invs.payment_breakdown(date.today(), date.today()).iloc[0]["Payment Method"] == "Cash"
