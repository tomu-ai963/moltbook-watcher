#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from flask import Flask, jsonify, render_template, request
from watcher import shared, start_watcher, stop_watcher, _lock, logger

app = Flask(__name__)

# Route Flask's logs to the same rotating file handler as the watcher.
for _h in logger.handlers:
    app.logger.addHandler(_h)
app.logger.setLevel(logging.INFO)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/state")
def api_state():
    with _lock:
        return jsonify({"running": shared["running"], "logs": shared["logs"][-50:],
                        "trend": shared["trend"][:10], "stats": dict(shared["stats"])})

@app.route("/api/posts")
def api_posts():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = min(100, max(1, int(request.args.get("limit", 20))))
    except (TypeError, ValueError):
        limit = 20
    with _lock:
        all_posts = list(shared["posts"])
    total = len(all_posts)
    start = (page - 1) * limit
    page_posts = all_posts[start:start + limit]
    return jsonify({"posts": page_posts, "page": page, "limit": limit,
                    "total": total, "has_more": start + limit < total})

@app.route("/api/start", methods=["POST"])
def api_start():
    start_watcher(); return jsonify({"ok": True})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    stop_watcher(); return jsonify({"ok": True})

@app.route("/api/clear", methods=["POST"])
def api_clear():
    with _lock:
        shared["logs"] = []
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("=" * 40)
    print(" Moltbook Watcher  http://localhost:5000")
    print("=" * 40)
    app.logger.info("Moltbook Watcher app starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
