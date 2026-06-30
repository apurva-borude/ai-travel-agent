"""Tiny Flask server so you can poke the agent from a browser.

    python3 server.py
    -> open http://127.0.0.1:8000

It serves one page (web/index.html) and one JSON endpoint (/api/evaluate).
Nothing fancy - it's just here for the demo.
"""

import json
import os

from flask import Flask, request, jsonify, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.claim import ClaimBuilder
from src.agent import ReimbursementAgent

app = Flask(__name__)
agent = ReimbursementAgent()

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/api/samples")
def samples():
    """Return the sample claim files so the UI can offer a dropdown."""
    out = {}
    folder = os.path.join(os.path.dirname(__file__), "data", "claims")
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            with open(os.path.join(folder, name)) as f:
                out[name] = json.load(f)
    return jsonify(out)


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    try:
        data = request.get_json(force=True)
        claim = ClaimBuilder.from_dict(data).build()
    except Exception as e:
        return jsonify({"error": "bad claim: %s" % e}), 400

    decision = agent.evaluate(claim)
    result = decision.to_dict()
    # report what actually happened: if the llm path errored out we'll see an
    # llm_error note in the trail and the rules engine produced the answer.
    fell_back = any("llm_error" in str(s.get("detail", "")) for s in decision.audit_trail)
    if not agent.llm.available or fell_back:
        result["_mode"] = "rules"
    else:
        result["_mode"] = "llm"
    return jsonify(result)


if __name__ == "__main__":
    mode = "LLM (Cerebras)" if agent.llm.available else "rules fallback"
    print("Agent mode:", mode)
    print("Open http://127.0.0.1:8000")
    # reloader off on purpose - it kept restarting mid-request during the demo
    app.run(port=8000, debug=False)
