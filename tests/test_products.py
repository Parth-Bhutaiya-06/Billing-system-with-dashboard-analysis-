import pytest

from services import inventory_service as svc
from services.inventory_service import ServiceError


def test_add_search_update_delete(db):
    pid = svc.add_product("Test Widget", "TST-1", "Gadgets", "10", "15.50", "18", 25, 5)
    assert svc.get_product(pid)["quantity"] == 25
    assert [p["id"] for p in svc.search_products("TST-1")] == [pid]
    assert [p["id"] for p in svc.search_products(str(pid))][0] == pid
    assert svc.search_products("", category="Gadgets")[0]["name"] == "Test Widget"

    svc.update_product(pid, "Test Widget 2", "TST-1", "Gadgets", "11", "16", "12", 7)
    p = svc.get_product(pid)
    assert p["name"] == "Test Widget 2" and float(p["selling_price"]) == 16.0

    assert svc.delete_product(pid) == "deleted"
    assert svc.get_product(pid) is None


def test_duplicate_sku_rejected(db):
    svc.add_product("A", "DUP-1", "", "1", "2", "0", 1, 0)
    with pytest.raises(ServiceError):
        svc.add_product("B", "DUP-1", "", "1", "2", "0", 1, 0)


def test_validation(db):
    with pytest.raises(ServiceError):
        svc.add_product("", "X", "", "1", "2", "0", 1, 0)
    with pytest.raises(ServiceError):
        svc.add_product("N", "X", "", "1", "2", "150", 1, 0)
    with pytest.raises(ServiceError):
        svc.add_product("N", "X", "", "-1", "2", "5", 1, 0)


def test_bike_management_and_description(db):
    bid = svc.add_bike("Hero HF Deluxe")
    with pytest.raises(ServiceError):
        svc.add_bike("hero hf deluxe")  # duplicate, ignoring case
    pid = svc.add_product("Clutch Wire", "CLW-1", "Engine", "40", "75", "18", 10, 2, bike_id=bid)
    assert svc.get_product(pid)["description"] == "Clutch Wire - Hero HF Deluxe"
    assert [p["id"] for p in svc.search_products("HF Deluxe")] == [pid]  # search by bike name
    assert [p["id"] for p in svc.search_products("", bike="Hero HF Deluxe")] == [pid]
    with pytest.raises(ServiceError):
        svc.delete_bike(bid)  # still used by a part
    svc.update_product(pid, "Clutch Wire", "CLW-1", "Engine", "40", "75", "18", 2, bike_id=None)
    assert svc.get_product(pid)["description"] == "Clutch Wire"
    svc.rename_bike(bid, "Hero HF Dawn")
    svc.delete_bike(bid)
    assert "Hero HF Dawn" not in [b["name"] for b in svc.list_bikes()]


def test_sold_product_is_deactivated_not_deleted(db):
    from services import billing_service as bs
    pid = svc.add_product("Sold Item", "SOLD-1", "", "5", "10", "5", 10, 1)
    bs.create_invoice([{"product_id": pid, "quantity": 1}])
    assert svc.delete_product(pid) == "deactivated"
    assert all(p["id"] != pid for p in svc.search_products(""))
