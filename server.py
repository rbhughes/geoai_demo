"""
Simple Flask server for GeoAI Demo.
"""

import io
import logging
import os
import re
from datetime import datetime, timezone

import yaml
from flask import Flask, jsonify, request, send_file, send_from_directory
from fpdf import FPDF

app = Flask(__name__)

INTENTS_DIR = "../api_v1/functions/ai/v1/intents"

# Bundled DejaVu Sans fonts — portable across all platforms
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONT_FAMILY = "DejaVu"


class ReportPDF(FPDF):
    """PDF generator that renders HTML content from the geoai_demo tabs."""

    def __init__(self):
        super().__init__()
        self.add_font(_FONT_FAMILY, "", os.path.join(_FONTS_DIR, "DejaVuSans.ttf"))
        self.add_font(_FONT_FAMILY, "B", os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf"))
        self.add_font(_FONT_FAMILY, "I", os.path.join(_FONTS_DIR, "DejaVuSans-Oblique.ttf"))
        self.add_font(_FONT_FAMILY, "BI", os.path.join(_FONTS_DIR, "DejaVuSans-BoldOblique.ttf"))
        self.set_font(_FONT_FAMILY, size=11)

    def header(self):
        self.set_font(_FONT_FAMILY, "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, "GeoAI Report", align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font(_FONT_FAMILY, "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def _sanitize_html_for_fpdf(html: str) -> str:
    """Clean up HTML so fpdf2's write_html can handle it.

    fpdf2.write_html supports a subset of HTML: h1-h6, p, b, i, u, br, hr,
    ul, ol, li, table, tr, th, td, a, img, font, code, pre, blockquote, sup, sub.
    We strip unsupported tags/attributes and normalize the content.
    """
    # Remove <div>, <span>, <section> wrappers — keep inner content
    html = re.sub(r"</?(?:div|span|section|article|nav|main|figure|figcaption)[^>]*>", "", html)

    # Remove class/style/id/data-* attributes (fpdf2 ignores them anyway)
    html = re.sub(r'\s+(?:class|style|id|data-[\w-]+)="[^"]*"', "", html)
    html = re.sub(r"\s+(?:class|style|id|data-[\w-]+)='[^']*'", "", html)

    # Convert <strong> to <b>, <em> to <i>
    html = re.sub(r"<(/?)strong[^>]*>", r"<\1b>", html)
    html = re.sub(r"<(/?)em[^>]*>", r"<\1i>", html)

    # Remove <button> elements entirely
    html = re.sub(r"<button[^>]*>.*?</button>", "", html, flags=re.DOTALL)

    # Remove empty paragraphs
    html = re.sub(r"<p>\s*</p>", "", html)

    # Convert <th> to bold <td> — fpdf2 tag_styles doesn't support <th> styling
    html = re.sub(r"<th\b[^>]*>", "<td><b>", html)
    html = re.sub(r"</th>", "</b></td>", html)

    # Add cellpadding and left-align to all tables so they render cleanly in fpdf2
    html = re.sub(r"<table\b([^>]*)>", r'<table\1 cellpadding="4" align="LEFT">', html)

    return html.strip()


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/intents")
def get_intents():
    """Load all intent YAML files and return structured data."""
    intents = []

    # Get all .yaml files except _config.yaml
    intent_dir = os.path.join(os.path.dirname(__file__), INTENTS_DIR)
    for filename in os.listdir(intent_dir):
        if filename.endswith(".yaml") and not filename.startswith("_"):
            filepath = os.path.join(intent_dir, filename)
            with open(filepath, "r") as f:
                intent_data = yaml.safe_load(f)
                intents.append(
                    {
                        "name": intent_data.get("name"),
                        "description": intent_data.get("description"),
                        "sections": intent_data.get("sections", {}).get("include", []),
                    }
                )

    # Sort so geologist comes first
    intents.sort(key=lambda x: (x["name"] != "geologist", x["name"]))

    return jsonify(intents)


@app.route("/api/export-pdf", methods=["POST"])
def export_pdf():
    """Convert HTML content to PDF and return the file."""
    data = request.get_json()
    if not data or not data.get("html"):
        return jsonify({"error": "html is required"}), 400

    html_content = data["html"]
    title = data.get("title", "export")

    clean_html = _sanitize_html_for_fpdf(html_content)

    try:
        pdf = ReportPDF()
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.write_html(
            clean_html,
            table_line_separators=True,
        )

        pdf_bytes = pdf.output()
        pdf_buffer = io.BytesIO(pdf_bytes)
    except Exception as e:
        logging.error(f"PDF generation failed: {e}", exc_info=True)
        return jsonify({"error": "PDF generation failed"}), 500

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    filename = f"{title}-{timestamp}.pdf"

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    app.run(port=8080, debug=True)
