"""Generate invoice PDFs (A4 and 80mm thermal) with ReportLab. Returns bytes.

Bill layout: shop name heading, customer name and date, then a table with
S.No, Part No., Description (part + bike name), Qty, Price and Total Amount.
"""
import io
import os
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

import config
from pdf.templates import (GRID, LIGHT, PRIMARY, THERMAL_WIDTH_MM, a4_styles, thermal_styles)
from utils.calculations import D, amount_in_words, money

R = config.CURRENCY


def _n(v):
    return f"{money(v):,.2f}"


def _m(v):
    return f"{R} {_n(v)}"


def _line_amount(item):
    """Qty x price, before bill-level discount and GST (those appear in the totals)."""
    return money(D(item["unit_price"]) * int(item["quantity"]))


def _logo(path, width_mm, height_mm):
    if path and os.path.exists(path):
        try:
            img = Image(path, width=width_mm * mm, height=height_mm * mm)
            img.hAlign = "CENTER"
            return img
        except Exception:
            return None
    return None


def _contact_lines(business):
    lines = []
    if business.get("business_address"):
        lines.append(escape(business["business_address"]))
    contact = []
    if business.get("business_phone"):
        contact.append(f"Phone: {escape(business['business_phone'])}")
    if business.get("business_email"):
        contact.append(f"Email: {escape(business['business_email'])}")
    if business.get("gstin"):
        contact.append(f"GSTIN: {escape(business['gstin'])}")
    if contact:
        lines.append("  |  ".join(contact))
    return lines


def generate_a4(invoice: dict, business: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm,
                            title=f"Invoice {invoice['invoice_number']}")
    st = a4_styles()
    shop = business.get("business_name", "")
    story = []

    # ---- heading: shop name (centred) with optional logo on the left
    centre = [Paragraph(escape(shop), st["shop"])]
    contact = _contact_lines(business)
    if contact:
        centre.append(Paragraph("<br/>".join(contact), st["biz_c"]))
    head = Table([[_logo(business.get("logo_path"), 20, 20) or "", centre, ""]],
                 colWidths=[24 * mm, 132 * mm, 24 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [head, Spacer(1, 3 * mm), HRFlowable(width="100%", color=PRIMARY, thickness=1.5),
              Spacer(1, 3 * mm)]

    # ---- customer name (left) and invoice no / date (right)
    cust = [f"<b>Customer Name:</b> {escape(invoice['customer_name'])}"]
    if invoice["customer_phone"]:
        cust.append(f"<b>Phone:</b> {escape(invoice['customer_phone'])}")
    if invoice["customer_address"]:
        cust.append(f"<b>Address:</b> {escape(invoice['customer_address'])}")
    meta = [f"<b>Invoice No:</b> {escape(invoice['invoice_number'])}",
            f"<b>Date:</b> {invoice['created_at'].strftime('%d-%b-%Y')}"]
    info = Table([[Paragraph("<br/>".join(cust), st["n"]), Paragraph("<br/>".join(meta), st["nr"])]],
                 colWidths=[120 * mm, 60 * mm])
    info.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                              ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [info, Spacer(1, 4 * mm)]

    # ---- items: S.No | Part No. | Description | Qty | Price | Total Amount
    data = [["S.No", "Part No.", "Description", "Qty", "Price", "Total Amount"]]
    for n, it in enumerate(invoice["items"], 1):
        data.append([str(n), Paragraph(escape(it["sku"]), st["cell"]),
                     Paragraph(escape(it["description"]), st["cell"]),
                     str(it["quantity"]), _n(it["unit_price"]), _n(_line_amount(it))])
    items = Table(data, colWidths=[13 * mm, 32 * mm, 70 * mm, 14 * mm, 24 * mm, 27 * mm], repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), LIGHT),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"), ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [None, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [items, Spacer(1, 4 * mm)]

    # ---- totals (discount / GST rows only when they apply)
    tot = [["Subtotal", _m(invoice["subtotal"])]]
    if money(invoice["discount_amount"]) > 0:
        tot.append(["Discount", "- " + _m(invoice["discount_amount"])])
    if money(invoice["gst_amount"]) > 0:
        tot.append(["GST", _m(invoice["gst_amount"])])
    tot.append(["GRAND TOTAL", _m(invoice["grand_total"])])
    tt = Table(tot, colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                            ("BACKGROUND", (0, -1), (-1, -1), PRIMARY),
                            ("TEXTCOLOR", (0, -1), (-1, -1), LIGHT),
                            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story += [tt, Spacer(1, 4 * mm),
              Paragraph(f"<b>Amount in words:</b> {amount_in_words(invoice['grand_total'])}", st["n"]),
              Paragraph(f"<b>Payment method:</b> {escape(invoice['payment_method'])}"
                        f"&nbsp;&nbsp;|&nbsp;&nbsp;<b>Served by:</b> {escape(invoice['employee_name'] or '-')}",
                        st["n"]),
              Spacer(1, 8 * mm)]

    sign = Table([["", [Paragraph(f"For <b>{escape(shop)}</b>", st["nr"]), Spacer(1, 14 * mm),
                        Paragraph("Authorised Signatory", st["nr"])]]],
                 colWidths=[110 * mm, 70 * mm])
    sign.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [sign, Spacer(1, 4 * mm), HRFlowable(width="100%", color=GRID, thickness=0.5),
              Spacer(1, 3 * mm), Paragraph(escape(business.get("invoice_footer", "Thank you!")), st["foot"])]
    doc.build(story)
    return buf.getvalue()


def generate_thermal(invoice: dict, business: dict) -> bytes:
    """80mm roll receipt; page height grows with the number of items."""
    st = thermal_styles()
    usable = THERMAL_WIDTH_MM * mm
    height = (125 + 12 * len(invoice["items"])) * mm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(80 * mm, height), leftMargin=4 * mm, rightMargin=4 * mm,
                            topMargin=4 * mm, bottomMargin=4 * mm,
                            title=f"Receipt {invoice['invoice_number']}")
    line = HRFlowable(width="100%", color=GRID, thickness=0.5, dash=(2, 2))
    story = []
    logo = _logo(business.get("logo_path"), 14, 14)
    if logo:
        story += [logo, Spacer(1, 1 * mm)]
    story.append(Paragraph(escape(business.get("business_name", "")), st["cb"]))
    for ln in _contact_lines(business):
        story.append(Paragraph(ln, st["c"]))
    story += [Spacer(1, 1.5 * mm), line, Spacer(1, 1 * mm),
              Paragraph(f"<b>Customer:</b> {escape(invoice['customer_name'])}", st["n"]),
              Paragraph(f"<b>Date:</b> {invoice['created_at'].strftime('%d-%b-%Y %H:%M')}", st["n"]),
              Paragraph(f"<b>Invoice No:</b> {escape(invoice['invoice_number'])}", st["n"]),
              Spacer(1, 1 * mm), line, Spacer(1, 1 * mm)]

    rows = [[Paragraph("<b>#</b>", st["n"]), Paragraph("<b>Part / Description</b>", st["n"]),
             Paragraph("<b>Qty</b>", st["r"]), Paragraph("<b>Amount</b>", st["r"])]]
    for n, it in enumerate(invoice["items"], 1):
        rows.append([Paragraph(str(n), st["n"]),
                     Paragraph(f"{escape(it['description'])}<br/>"
                               f"<font size=6.5>Part No: {escape(it['sku'])}  @ {_n(it['unit_price'])}</font>",
                               st["n"]),
                     Paragraph(str(it["quantity"]), st["r"]),
                     Paragraph(_n(_line_amount(it)), st["r"])])
    t = Table(rows, colWidths=[usable * 0.09, usable * 0.51, usable * 0.10, usable * 0.30])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [t, Spacer(1, 1 * mm), line, Spacer(1, 1 * mm)]

    tot = [[Paragraph("Subtotal", st["n"]), Paragraph(_n(invoice["subtotal"]), st["r"])]]
    if money(invoice["discount_amount"]) > 0:
        tot.append([Paragraph("Discount", st["n"]), Paragraph("- " + _n(invoice["discount_amount"]), st["r"])])
    if money(invoice["gst_amount"]) > 0:
        tot.append([Paragraph("GST", st["n"]), Paragraph(_n(invoice["gst_amount"]), st["r"])])
    tot.append([Paragraph("TOTAL", st["nb"]), Paragraph(_m(invoice["grand_total"]), st["rb"])])
    tt = Table(tot, colWidths=[usable * 0.5, usable * 0.5])
    tt.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("LINEABOVE", (0, -1), (-1, -1), 0.8, PRIMARY)]))
    story += [tt, Spacer(1, 1 * mm),
              Paragraph(f"<b>Paid by:</b> {escape(invoice['payment_method'])}", st["n"]),
              Paragraph(amount_in_words(invoice["grand_total"]), st["n"]),
              Spacer(1, 2 * mm), line, Spacer(1, 1.5 * mm),
              Paragraph(escape(business.get("invoice_footer", "Thank you!")), st["c"])]
    doc.build(story)
    return buf.getvalue()


def generate_invoice_pdf(invoice: dict, business: dict, fmt: str = "A4") -> bytes:
    return generate_thermal(invoice, business) if fmt.lower().startswith(("80", "thermal")) \
        else generate_a4(invoice, business)
