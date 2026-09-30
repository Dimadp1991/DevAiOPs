import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# 1. Configuration & Fallbacks matching your K8s environment
WEBHOOK_SECRET = "gogs-secret-token"

# Internal cluster URL routing to your Jenkins service in devops-core
JENKINS_URL = os.getenv("JENKINS_URL", "http://jenkins.devops-core.svc.cluster.local:8080")
# JENKINS_USER = os.getenv("JENKINS_USER")
# JENKINS_TOKEN = os.getenv("JENKINS_TOKEN")

JENKINS_USER = "admin"
JENKINS_TOKEN = "admin"

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    # Verify token from query parameters
    token = request.args.get("token")
    if token != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 403

    # Get the Jenkins job name from URL parameters
    job_name = request.args.get("job")
    if not job_name:
        return jsonify({"error": "Missing 'job' query parameter"}), 400

    # Parse incoming JSON payload from Gogs
    payload = request.json or {}
    event = request.headers.get("X-Gogs-Event", "unknown")

    print(f"--- WEBHOOK RECEIVED ---")
    print(f"Event Header: {event}")
    print(f"Payload Action: {payload.get('action')}")
    print(f"Full Payload Keys: {list(payload.keys())}")

    # Check for Pull Request Merge event or general PR events
    is_triggered = False

    # If Gogs sends a pull_request event
    if event in ["pull_request", "pull"]:
        action = payload.get("action")
        pull_request = payload.get("pull_request", {})
        merged = pull_request.get("merged", False)

        print(f"PR Action: {action}, Merged Status: {merged}")

        # Trigger if merged is True, or if action indicates a merge/close
        if merged or action in ["closed", "merged"]:
            is_triggered = True
            print("Condition matched: Pull Request was merged or closed.")

    # Fallback/Safety check: If you want to test quickly or if your Gogs setup sends a push on merge branch update
    elif event == "push":
        branch = payload.get("ref", "")
        print(f"Push ref received: {branch}")
        # If it's a push directly to main/master from a merge
        if "main" in branch or "master" in branch:
            # Uncomment the line below if you want fallback pushes to main to trigger it:
            # is_triggered = True
            pass

    if is_triggered:
        # Construct URLs
        crumb_url = f"{JENKINS_URL}/crumbIssuer/api/json"
        jenkins_api_url = f"{JENKINS_URL}/job/{job_name}/build"

        # Use requests.Session to maintain authentication headers
        session = requests.Session()
        session.auth = (JENKINS_USER, JENKINS_TOKEN)

        try:
            headers = {}
            crumb_response = session.get(crumb_url, timeout=5)
            if crumb_response.status_code == 200:
                crumb_data = crumb_response.json()
                headers[crumb_data['crumbRequestField']] = crumb_data['crumb']
                print("Successfully obtained CSRF Crumb.")
            else:
                print(
                    f"Warning: Could not get crumb (Status: {crumb_response.status_code}). Attempting build without it.")

            response = session.post(
                jenkins_api_url,
                headers=headers,
                timeout=5
            )

            if response.status_code in [200, 201, 202]:
                print(f"Successfully triggered Jenkins job: {job_name}")
            else:
                print(f"Failed to trigger Jenkins. Status code: {response.status_code}, Response: {response.text}")
                return jsonify({
                    "error": "Failed to trigger Jenkins",
                    "details": response.text
                }), 502

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Jenkins: {e}")
            return jsonify({"error": "Internal connection error to Jenkins"}), 500
    else:
        print("Event ignored: Did not match merge criteria.")

    return jsonify({"status": "success", "triggered": is_triggered, "job": job_name}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)