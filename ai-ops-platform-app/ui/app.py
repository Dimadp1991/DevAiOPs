import os
from datetime import datetime

import httpx
from flask import Flask, abort, render_template, request

API_BASE = os.getenv("AIOPS_API_URL", "http://aiops-llm-app.devops-core.svc.cluster.local:8080")

app = Flask(__name__)


def _api_get(path: str) -> dict | list:
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def _api_post(path: str, json: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json=json or {})
        resp.raise_for_status()
        return resp.json()


def _format_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


@app.context_processor
def inject_helpers():
    return {"format_dt": _format_dt}


@app.route("/")
def dashboard():
    try:
        incidents = _api_get("/api/v1/incidents")
    except httpx.HTTPError:
        incidents = []
    return render_template("dashboard.html", incidents=incidents)


@app.route("/incidents/<incident_id>")
def incident_detail(incident_id: str):
    try:
        incident = _api_get(f"/api/v1/incidents/{incident_id}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            abort(404)
        raise
    return render_template("incident_detail.html", incident=incident)


@app.route("/incidents/<incident_id>/enrich", methods=["POST"])
def enrich_incident(incident_id: str):
    try:
        _api_post(f"/api/v1/incidents/{incident_id}/enrich")
    except httpx.HTTPError:
        pass
    return incident_detail(incident_id)


@app.route("/incidents/<incident_id>/remediate", methods=["POST"])
def remediate_incident(incident_id: str):
    action = request.form.get("action", "all")
    try:
        _api_post(f"/api/v1/incidents/{incident_id}/remediate", json={"action": action})
    except httpx.HTTPError:
        pass
    return incident_detail(incident_id)


@app.route("/health")
def health():
    return {"status": "ok", "service": "aiops-ui"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
