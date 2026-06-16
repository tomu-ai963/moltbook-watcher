#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, jsonify, render_template
from watcher import shared, start_watcher, stop_watcher, _lock

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/state")
def api_state():
    with _lock:
        return jsonify({"running": shared["running"], "logs": shared["logs"][-50:],
                        "posts": shared["posts"][:30], "trend": shared["trend"][:10],
                        "stats": dict(shared["stats"])})

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
    app.run(host="0.0.0.0", port=5000, debug=False)
