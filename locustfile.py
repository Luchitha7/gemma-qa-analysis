"""Load test for the QA web API, using Locust.

Each simulated user repeatedly calls the API. Tasks are tagged so you can
stress a subset:

    # start the app first (in another terminal):
    #   python web_app.py

    # light endpoints only (safe, no models needed beyond a running server):
    locust -f locustfile.py --tags light

    # the heavy endpoint (needs Ollama running; expect it to be slow):
    locust -f locustfile.py --tags heavy

    # everything:
    locust -f locustfile.py

Then open http://localhost:8089, set the number of users and spawn rate,
and click Start. Watch requests/sec, response times, and failures live.

Note on rate limiting: if you are testing a build that has the slowapi
limits enabled, a single machine is one IP, so /analyze will hit HTTP 429
almost immediately and those show up as failures. For a pure performance
test, run against a build with the limits relaxed or removed.
"""

from locust import HttpUser, task, tag, between

# One turn per line; a small, realistic support call for /analyze.
SAMPLE_TRANSCRIPT = (
    "[00:00] Agent: Thank you for calling HomeNet support, how can I help?\n"
    "[00:06] Client: I was charged twice this month and I want it fixed.\n"
    "[00:09] Agent: I'm sorry about that. Let me pull up your account.\n"
    "[00:31] Agent: I can see the duplicate charge. I've refunded it now.\n"
    "[00:43] Client: Alright, thank you."
)

# A pre-computed result so /report can be tested on its light path (just
# rendering a PDF) without re-running the whole scoring pipeline.
SAMPLE_RESULT = {
    "final": 78.4, "agent": 82.0, "conversation": 71.0, "band": "OKAY",
    "accuracy_overall": 80.0, "compliance_score": 75.0,
    "response_time_score": 88.0, "summary": "Load-test sample result.",
    "ratings": [{"name": "Resolution", "rating": "PASS",
                 "reason": "Issue resolved on the call."}],
    "compliance": [{"rule": "Greeting", "status": "OK", "evidence": "Hi"}],
    "accuracy": [], "suggestions": ["Verify identity before account changes."],
}

# Default weights payload for POST /weights.
SAMPLE_WEIGHTS = {
    "agent": 0.45, "accuracy": 0.20, "compliance": 0.20,
    "conversation": 0.10, "response_time": 0.05,
}


class QAUser(HttpUser):
    """One simulated user of the QA API."""

    # Default target; override with --host on the command line if needed.
    host = "http://localhost:8000"

    # Wait 1 to 3 seconds between actions, like a real person clicking around.
    wait_time = between(1, 3)

    @tag("light")
    @task(5)  # called most often: the cheapest, most common read
    def read_weights(self):
        self.client.get("/weights", name="GET /weights")

    @tag("light")
    @task(1)
    def save_weights(self):
        self.client.post("/weights", json=SAMPLE_WEIGHTS, name="POST /weights")

    @tag("light")
    @task(1)
    def download_report(self):
        # Sends a ready-made result, so this exercises the PDF rendering only.
        self.client.post("/report", json=SAMPLE_RESULT, name="POST /report")

    @tag("heavy")
    @task(1)
    def analyze(self):
        # The expensive path: Gemma + RoBERTa + RAG. Expect seconds per call.
        self.client.post("/analyze",
                         json={"transcript": SAMPLE_TRANSCRIPT},
                         name="POST /analyze")

    @tag("queue")
    @task(1)
    def submit_job(self):
        # The queued path: the request is accepted instantly and lined up,
        # so even a burst of users gets a fast reply and the model is never
        # hit by more than QA_MAX_CONCURRENT scores at once. Compare this to
        # the 'heavy' tag: same 150 users, but here nothing overloads.
        #
        # Under capacity limits, a full system replies 503 "busy, retry
        # shortly". That is the endpoint working as designed, not an error, so
        # we count both 200 (accepted) and 503 (politely turned away) as
        # success. Only other codes are real failures.
        with self.client.post("/jobs",
                              json={"transcript": SAMPLE_TRANSCRIPT},
                              name="POST /jobs",
                              catch_response=True) as resp:
            if resp.status_code in (200, 503):
                resp.success()
            else:
                resp.failure(f"unexpected status {resp.status_code}")
