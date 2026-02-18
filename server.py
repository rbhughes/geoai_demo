"""
Simple Flask server for GeoAI Demo.
"""

import os

import yaml
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

INTENTS_DIR = "../api_v1/functions/gemini_api/v3/intents"


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


if __name__ == "__main__":
    app.run(port=8080, debug=True)
