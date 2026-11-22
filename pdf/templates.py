"""Shared colours, fonts and paragraph styles for invoice PDFs."""
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

PRIMARY = colors.HexColor("#1f4e79")
LIGHT = colors.HexColor("#eaf1f8")
GRID = colors.HexColor("#c9d3de")
TEXT = colors.HexColor("#1f2d3d")

# 80mm thermal paper printable width
THERMAL_WIDTH_MM = 72


def a4_styles():
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20, textColor=PRIMARY),
        "shop": ParagraphStyle("shop", fontName="Helvetica-Bold", fontSize=24, leading=28,
                               textColor=PRIMARY, alignment=TA_CENTER),
        "biz_c": ParagraphStyle("biz_c", fontName="Helvetica", fontSize=9, leading=12,
                                textColor=TEXT, alignment=TA_CENTER),
        "biz": ParagraphStyle("biz", fontName="Helvetica", fontSize=9, leading=12, textColor=TEXT),
        "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10, textColor=PRIMARY),
        "n": ParagraphStyle("n", fontName="Helvetica", fontSize=9, leading=12, textColor=TEXT),
        "nr": ParagraphStyle("nr", fontName="Helvetica", fontSize=9, leading=12,
                             textColor=TEXT, alignment=TA_RIGHT),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, leading=11, textColor=TEXT),
        "foot": ParagraphStyle("foot", fontName="Helvetica-Oblique", fontSize=10,
                               textColor=PRIMARY, alignment=TA_CENTER),
    }


def thermal_styles():
    return {
        "c": ParagraphStyle("c", fontName="Helvetica", fontSize=7.5, leading=9.5, alignment=TA_CENTER),
        "cb": ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_CENTER),
        "n": ParagraphStyle("n", fontName="Helvetica", fontSize=7.5, leading=9.5),
        "nb": ParagraphStyle("nb", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5),
        "r": ParagraphStyle("r", fontName="Helvetica", fontSize=7.5, leading=9.5, alignment=TA_RIGHT),
        "rb": ParagraphStyle("rb", fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, alignment=TA_RIGHT),
    }
