# Bapasitaram Auto Parts - Billing and Inventory Management

A single-shop billing, invoicing and inventory system built with Python, Streamlit,
SQLite, SQLAlchemy, Pandas, ReportLab and Plotly.

## Default login (change after first sign-in)

| Role     | Username  | Password   |
|----------|-----------|------------|
| Admin    | `admin`   | `admin123` |
| Employee | `cashier` | `cashier123` |

Passwords are stored only as salted PBKDF2-SHA256 hashes. Change them under **Employees**.

## Install and run (Windows PowerShell)

```powershell
cd billing_system
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks activation, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

macOS / Linux: `python3 -m venv venv && source venv/bin/activate`, then the same pip / streamlit commands.

The app opens at http://localhost:8501. The database file `billing.db` and sample data
(13 products, 2 customers, categories, business settings) are created automatically on first run.
Data persists between restarts.

## Run the tests

```powershell
python -m pytest tests -v
```

## Features

- **Dashboard** - today's sales, totals, low-stock alerts, daily/monthly charts, top sellers, recent invoices (all from the database).
- **New Bill** - search products, cart with editable quantities, customer select/add, discount (amount or percent), GST, payment method, automatic invoice numbers (`INV-YYYYMMDD-0001`), blocked when stock is insufficient.
- **Invoices** - A4 and 80mm thermal PDFs with logo, business info, items, GST, totals, amount in words and footer. Download, then print from your PDF viewer (Ctrl+P).
- **Invoice History** - search by number/customer, date filter, details, re-download. Invoices store frozen copies of prices, GST and customer details, so later edits never change them.
- **Products / Inventory / Customers / Reports / Employees / Settings** - full CRUD, stock add/reduce/set with history, CSV exports, role-based access.

## Auto-parts bill layout

Top of every bill: **Bapasitaram Auto Parts** (the shop name is editable in Settings), then the
customer name and date. The bill table columns are **S.No, Part No., Description, Qty, Price, Total Amount**.
The Description is the part name followed by the bike it fits, for example `Air Filter - Honda Shine`.

- **Bikes** are added by the administrator under Products > Bikes (add, rename, delete). Pick a bike when adding or editing a part.
- On the New Bill page you can search by part no., description or bike name, and filter by bike.
- Type a customer name for walk-in customers, or choose / add a saved customer.
- Before first use, open Settings and enter your shop address, phone number and logo so they print on the invoice.
- Databases from the previous version are upgraded automatically when the app starts.

## Design notes

- All money uses `Decimal`; GST is added on top of the discounted price (GST-exclusive pricing). A bill-level discount is spread proportionally across lines so GST stays correct.
- Invoice, items, payment and stock deduction are saved in a single transaction; any failure rolls everything back.
- Products or customers that already appear on invoices are deactivated rather than deleted, to keep history intact.
- Employees can use Dashboard, New Bill, Products, Inventory, Customers and Invoice History. Only admins see Reports, Employees and Settings and can delete products.
- Currency is shown as `Rs.` (change `CURRENCY` in `config.py`).

## Structure

```
app.py  config.py  requirements.txt
database/  connection.py  models.py  init_db.py
services/  billing_service.py  inventory_service.py  invoice_service.py
modules/   dashboard products inventory billing customers invoices reports employees settings
pdf/       invoice_generator.py  templates.py
utils/     calculations.py  authentication.py  helpers.py
tests/     test_products.py  test_billing.py  test_inventory.py
```
