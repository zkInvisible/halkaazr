"""Yerel web arayüzü için Flask API ve statik dosya sunucusu."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data.sources import SourceError
from main import load_report, refresh_report


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def frontend_asset(filename: str):
        return send_from_directory(FRONTEND_DIR, filename)

    @app.get("/api/report")
    def report():
        current = load_report()
        if not current:
            try:
                current = refresh_report()
            except SourceError as error:
                return jsonify({"error": str(error)}), 503
        return jsonify(current)

    @app.post("/api/refresh")
    def refresh():
        try:
            return jsonify(refresh_report(force_market_refresh=True))
        except SourceError as error:
            return jsonify({"error": str(error)}), 503

    # Background thread for keep-alive and daily auto-refresh
    def background_tasks():
        url = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:5050")
        last_refresh_time = time.time()
        
        while True:
            time.sleep(14 * 60)  # Ping every 14 minutes
            try:
                requests.get(url, timeout=10)
            except Exception:
                pass
                
            # Gunde 1 kere (24 saatte bir) otomatik veriyi yenile
            if time.time() - last_refresh_time > 24 * 60 * 60:
                print("Running daily auto-refresh...")
                try:
                    refresh_report(force_market_refresh=True)
                    last_refresh_time = time.time()
                except Exception as e:
                    print(f"Auto-refresh failed: {e}")

    threading.Thread(target=background_tasks, daemon=True).start()

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
