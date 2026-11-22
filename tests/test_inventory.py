import pytest

from services import inventory_service as svc
from services.inventory_service import ServiceError


def _pid():
    return svc.search_products("ENG-3001")[0]["id"]


def test_add_reduce_set_and_history(db):
    pid = _pid()
    start = svc.get_product(pid)["quantity"]
    svc.adjust_stock(pid, "add", 10, "delivery", "tester")
    svc.adjust_stock(pid, "reduce", 4, "damaged", "tester")
    assert svc.get_product(pid)["quantity"] == start + 6
    svc.adjust_stock(pid, "set", 50, "recount", "tester")
    assert svc.get_product(pid)["quantity"] == 50
    hist = svc.stock_history(pid)
    assert len(hist) >= 4 and hist[0]["New"] == 50 and hist[0]["User"] == "tester"


def test_cannot_reduce_below_zero(db):
    pid = _pid()
    qty = svc.get_product(pid)["quantity"]
    with pytest.raises(ServiceError):
        svc.adjust_stock(pid, "reduce", qty + 1)
    assert svc.get_product(pid)["quantity"] == qty


def test_low_stock_and_inventory_value(db):
    low = [p["sku"] for p in svc.low_stock_products()]
    assert "LUB-5002" in low and "ELC-4003" in low  # seeded below minimum
    cost, retail = svc.inventory_value()
    assert retail > cost > 0
    pid = svc.search_products("LUB-5002")[0]["id"]
    svc.adjust_stock(pid, "add", 100)
    assert "LUB-5002" not in [p["sku"] for p in svc.low_stock_products()]
