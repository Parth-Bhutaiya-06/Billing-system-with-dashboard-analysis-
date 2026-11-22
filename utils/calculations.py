"""Decimal-based money maths and amount-in-words."""
from decimal import Decimal, ROUND_HALF_UP

TWO = Decimal("0.01")


def D(value) -> Decimal:
    """Safe Decimal conversion (never goes through float formatting errors)."""
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(TWO, rounding=ROUND_HALF_UP)


def calculate_line(unit_price, quantity, discount_amount, gst_percent) -> dict:
    """GST-exclusive pricing: GST is added on top of (price*qty - discount).

    Returns taxable value, gst amount and line total (taxable + gst).
    """
    gross = money(D(unit_price) * int(quantity))
    discount = money(discount_amount)
    if discount < 0:
        raise ValueError("Discount cannot be negative")
    if discount > gross:
        raise ValueError("Discount cannot exceed the line amount")
    taxable = gross - discount
    gst = money(taxable * D(gst_percent) / Decimal("100"))
    return {"gross": gross, "discount": discount, "taxable": taxable,
            "gst": gst, "total": taxable + gst}


def allocate_discount(lines, discount_type, discount_value):
    """Spread a bill-level discount across lines proportionally to gross.

    lines: list of dicts with 'unit_price' and 'quantity'.
    discount_type: 'amount' or 'percent'. Returns list of Decimal discounts that
    sum exactly to the total discount.
    """
    grosses = [money(D(l["unit_price"]) * int(l["quantity"])) for l in lines]
    subtotal = sum(grosses, Decimal("0"))
    if subtotal <= 0:
        return [Decimal("0.00") for _ in lines]
    value = D(discount_value)
    if value < 0:
        raise ValueError("Discount cannot be negative")
    total_discount = money(subtotal * value / Decimal("100")) if discount_type == "percent" \
        else money(value)
    if total_discount > subtotal:
        raise ValueError("Discount cannot exceed the subtotal")
    shares, allocated = [], Decimal("0")
    for i, g in enumerate(grosses):
        if i == len(grosses) - 1:
            share = total_discount - allocated  # remainder goes to last line
        else:
            share = money(total_discount * g / subtotal)
        shares.append(share)
        allocated += share
    return shares


def calculate_invoice(lines, discount_type="amount", discount_value=0) -> dict:
    """Compute full invoice totals. lines: dicts with unit_price, quantity, gst_percent."""
    shares = allocate_discount(lines, discount_type, discount_value)
    computed, subtotal, disc, gst, total = [], Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
    for line, share in zip(lines, shares):
        c = calculate_line(line["unit_price"], line["quantity"], share, line["gst_percent"])
        computed.append(c)
        subtotal += c["gross"]
        disc += c["discount"]
        gst += c["gst"]
        total += c["total"]
    return {"lines": computed, "subtotal": money(subtotal), "discount": money(disc),
            "gst": money(gst), "grand_total": money(total)}


# ---------------------------------------------------------------- words
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_thousand(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))
    elif n > 0:
        parts.append(_ONES[n])
    return " ".join(parts)


def _int_to_words(n: int) -> str:
    """Indian numbering system (crore, lakh, thousand)."""
    if n == 0:
        return "Zero"
    parts = []
    for value, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if n >= value:
            parts.append(_below_thousand(n // value) + " " + name)
            n %= value
    if n:
        parts.append(_below_thousand(n))
    return " ".join(parts)


def amount_in_words(amount) -> str:
    amount = money(amount)
    rupees = int(amount)
    paise = int((amount - rupees) * 100)
    words = f"Rupees {_int_to_words(rupees)}"
    if paise:
        words += f" and {_int_to_words(paise)} Paise"
    return words + " Only"
