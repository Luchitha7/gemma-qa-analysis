"""WEB VERSION of the QA analysis.

Paste a call transcript in the browser, click Analyze, and get the full styled
QA report (final score, agent scorecard, summary, tense moments, suggestions).

It reuses the exact same pipeline as qa_report.py -- nothing new is analysed
here, it's just a web front-end over the parts we already built.

    python web_app.py
    # then open http://localhost:8000

Requires Ollama running ('brew services start ollama') and the venv active.
"""

import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

import job_queue

from gemma_client import gemma, reset_token_usage, get_token_usage
from qa_intensity import analyze
from qa_agent import (
    RATING_SCORES, agent_harsh_lines, apply_tone_penalty, build_prompt,
    conversation_score, final_qa_score, parse_ratings,
)
from qa_summary import SUMMARY_PROMPT
from qa_suggestions import SUGGESTIONS_PROMPT, clean_suggestions, suggestions_to_list
from rag_accuracy import check_accuracy
from rag_compliance import check_compliance
from response_time import (
    leading_time_seconds, response_delays, response_time_score,
)
from weights_config import load_weights, save_weights
from report_pdf import build_report

app = FastAPI()


class TranscriptIn(BaseModel):
    transcript: str


# Different transcripts name the two sides differently. Map them to a
# consistent "Agent" / "Client" so the rest of the pipeline works the same.
AGENT_LABELS = {"agent", "ai", "bot", "assistant", "rep", "representative",
                "support", "operator", "advisor"}
CLIENT_LABELS = {"client", "customer", "caller", "user", "member", "subscriber"}

# Leading timestamp like "[00:15]", "[00:15:03]" or "(00:15)".
TIMESTAMP_RE = re.compile(r"^[\[\(]\s*\d{1,2}:\d{2}(?::\d{2})?\s*[\]\)]\s*")
# A whole line that is just a bracketed note, e.g. "[Latency: 1.8s ...]".
NOTE_LINE_RE = re.compile(r"^[\[\(].*[\]\)]$")
# A leading stage-direction inside the text, e.g. "[Frustrated] No!".
STAGE_DIR_RE = re.compile(r"^[\[\(][^\]\)]*[\]\)]\s*")


def normalize_speaker(name):
    """Map a raw speaker label to 'Agent'/'Client', or keep it if unknown."""
    key = name.strip().lower()
    if key in AGENT_LABELS:
        return "Agent"
    if key in CLIENT_LABELS:
        return "Client"
    return name.strip()


def parse_transcript(raw):
    """Turn pasted text into [(speaker, text), ...].

    Handles several common transcript styles:
      - plain 'Agent: hello' / 'Client: hi'
      - timestamped 'Client: hi', '[00:15] Client: hi', '(00:15) AI: hi'
      - bot labels ('AI', 'Bot', 'Assistant') and 'Customer'/'Caller' etc.
    It drops note-only lines like '[Latency: 1.8s ...]' and strips leading
    stage directions like '[Frustrated]'. A line with no recognised speaker is
    attached to the previous turn (so a wrapped sentence still works).
    """
    turns = []
    times = []               # seconds (or None) for each turn, kept aligned
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # read a leading timestamp (if any) BEFORE we strip it off
        t = leading_time_seconds(line)
        line = TIMESTAMP_RE.sub("", line).strip()
        if not line:
            continue

        # a line that is only a bracketed note (e.g. "[Latency: ...]") is skipped
        if NOTE_LINE_RE.match(line):
            continue

        if ":" in line:
            speaker, text = line.split(":", 1)
            speaker, text = speaker.strip(), text.strip()
            text = STAGE_DIR_RE.sub("", text).strip()  # drop "[Frustrated]" etc.
            if speaker and len(speaker) <= 20 and text:
                turns.append((normalize_speaker(speaker), text))
                times.append(t)
                continue

        # no clear speaker -> tack onto the previous turn
        if turns:
            prev_speaker, prev_text = turns[-1]
            turns[-1] = (prev_speaker, f"{prev_text} {line}".strip())
    return turns, times


def band(score):
    if score >= 80:
        return "GOOD"
    if score >= 60:
        return "OKAY"
    return "NEEDS IMPROVEMENT"


def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


def run_pipeline(transcript, times=None):
    """Same steps as qa_report.py, returned as a dict for the web page."""
    transcript_text = format_transcript(transcript)
    if times is None:
        times = [None] * len(transcript)

    # RoBERTa: sentiment + tense moments
    rows = analyze(transcript)
    intense = [r for r in rows if r["intense"]]

    # Gemma: three small calls. Reset the token tally first so we can measure
    # exactly how many tokens this one report used.
    reset_token_usage()
    harsh = agent_harsh_lines(rows)
    summary = gemma(SUMMARY_PROMPT.format(transcript=transcript_text),
                    label="summary")
    ratings = apply_tone_penalty(
        parse_ratings(gemma(build_prompt(transcript_text, intense, harsh),
                            label="scorecard")), harsh)
    suggestions = clean_suggestions(
        gemma(SUGGESTIONS_PROMPT.format(transcript=transcript_text),
              label="suggestions"))
    token_usage = get_token_usage()

    # RAG: how accurate were the agent's answers vs the ideal answers?
    accuracy_results, accuracy_overall = check_accuracy(transcript)
    # RAG: did the agent break any compliance rules? (token-free)
    compliance_results, compliance_score = check_compliance(transcript)
    # Timestamps: how fast did the agent reply? (token-free)
    delays = response_delays(transcript, times)
    rt_score = response_time_score(delays)

    # Scores. Load the current weights (the saved file if present, otherwise
    # the code defaults) so a change made from the frontend takes effect here.
    weights = load_weights()
    rated = [RATING_SCORES[r["rating"]] for r in ratings if r["rating"]]
    agent = round(sum(rated) / len(rated), 1) if rated else 0.0
    conv = conversation_score(rows)
    final = final_qa_score(agent, conv, accuracy_overall,
                           compliance_score, rt_score, weights=weights)

    # How the transcript was read (so a mis-parse can't hide behind a score).
    agent_lines = sum(1 for s, _ in transcript if s.lower() == "agent")
    client_lines = sum(1 for s, _ in transcript if s.lower() == "client")
    warning = ""
    if client_lines == 0:
        warning = ("No client lines were detected, so the conversation score is "
                   "a neutral default — the final score may not be reliable. "
                   "Check the transcript uses 'Client:' (or Customer/Caller).")

    return {
        "final": final,
        "agent": agent,
        "conversation": conv,
        "band": band(final),
        "parsed": {"turns": len(transcript),
                   "agent": agent_lines, "client": client_lines},
        "token_usage": token_usage,
        "warning": warning,
        "summary": summary,
        "ratings": [
            {
                "name": r["name"],
                "rating": r["rating"] or "UNRATED",
                "reason": r["reason"],
            }
            for r in ratings
        ],
        "intense": [
            {
                "turn": r["turn"],
                "speaker": r["speaker"],
                "sentiment": r["sentiment"],
                "text": r["text"],
            }
            for r in intense
        ],
        "suggestions": suggestions_to_list(suggestions),
        "compliance_score": compliance_score,
        "compliance": compliance_results,
        "response_time_score": rt_score,
        "response_times": [
            {
                "agent_turn": d["agent_turn"],
                "delay": d["delay"],
                "slow": d["slow"],
                "client_text": d["client_text"],
                "agent_text": d["agent_text"],
            }
            for d in delays
        ],
        "accuracy_overall": accuracy_overall,
        "accuracy": [
            {
                "client_question": r["client_question"],
                "matched_question": r["matched_question"],
                "confidence": r["confidence"],
                "agent_answer": r["agent_answer"],
                "ideal_answer": r["ideal_answer"],
                "covered": r["covered"],
                "missed": r["missed"],
                "accuracy": round(r["accuracy"] * 100, 1),
            }
            for r in accuracy_results
        ],
    }


@app.post("/analyze")
def analyze_call(payload: TranscriptIn):
    transcript, times = parse_transcript(payload.transcript)
    if not transcript:
        return {"error": "No transcript lines found. Use 'Agent: ...' and "
                         "'Client: ...' on separate lines."}
    return run_pipeline(transcript, times)


def score_job(transcript_text):
    """Score one transcript. Run by the queue's workers, not by a request.

    Raises on a bad transcript so the job is marked 'error' with the reason,
    instead of returning a normal-looking result.
    """
    transcript, times = parse_transcript(transcript_text)
    if not transcript:
        raise ValueError("No transcript lines found. Use 'Agent: ...' and "
                         "'Client: ...' on separate lines.")
    return run_pipeline(transcript, times)


# Start the fixed pool of workers that drain the queue. Done once, at import.
job_queue.start_workers(score_job)


@app.post("/jobs")
def submit_job(payload: TranscriptIn):
    """Queue a transcript for scoring and return its job id immediately.

    This is the safe way to score at scale: the request is accepted and lined
    up instead of hitting the model straight away, so a burst of requests can
    never overload the machine. Poll GET /jobs/{id} for the result.

    If the system is already at capacity, the request is turned away with a
    503 and a Retry-After header rather than being queued, so the app never
    builds up a huge backlog. The caller should wait and try again.
    """
    ok, info = job_queue.submit(payload.transcript)
    if not ok:
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": str(info["retry_after"])},
            content={
                "status": "busy",
                "message": "The scorer is at capacity. Please retry shortly.",
                "processing": info["processing"],
                "waiting": info["waiting"],
                "capacity": info["capacity"],
                "retry_after_seconds": info["retry_after"],
            },
        )
    return info


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    """Fetch a job by id: its status, and the result once it is done."""
    job = job_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No job with that id.")
    return job


@app.get("/jobs")
def list_jobs():
    """The whole queue at a glance: how many are waiting, running, and done."""
    return job_queue.snapshot()


@app.get("/queue", response_class=HTMLResponse)
def queue_monitor():
    """A live dashboard for demos: watch the queue fill and drain in real time.

    Polls GET /jobs every second and can fire a burst of requests at POST /jobs
    so a room can see, at a glance, that the system takes on only what it can
    (capacity), scores a couple at a time, and turns the rest away with a
    polite 'busy' rather than overloading.
    """
    return QUEUE_PAGE


QUEUE_PAGE = """
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SignalQA - Queue monitor</title>
  <style>
    :root { --cream:#fbf9f4; --ink:#1b1c19; --muted:#444748; --faint:#747878;
            --line:#c4c7c7; --beige:#eae8e3; --amber:#f0e0ca; --amber-ink:#6b4e12;
            --green-bg:#d9e7dd; --green-ink:#2f4a38; --red:#ba1a1a; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--cream); color:var(--ink);
           font-family:-apple-system,'Hanken Grotesk',sans-serif; }
    .wrap { max-width:1080px; margin:0 auto; padding:40px 32px 80px; }
    h1 { font-weight:600; font-size:26px; margin:0 0 4px; }
    .sub { color:var(--faint); font-size:14px; margin-bottom:28px; }
    .cards { display:grid; grid-template-columns:repeat(6,1fr); gap:14px; margin-bottom:26px; }
    @media (max-width:820px){ .cards{ grid-template-columns:repeat(3,1fr);} }
    .card { border:0.5px solid var(--line); background:#fff; padding:16px 18px; }
    .card .n { font-size:30px; font-weight:600; line-height:1; }
    .card .l { font-size:11px; letter-spacing:0.08em; text-transform:uppercase;
               color:var(--faint); margin-top:8px; }
    .card.hot .n { color:var(--amber-ink); }
    .card.free .n { color:var(--green-ink); }
    .controls { display:flex; align-items:center; gap:16px; flex-wrap:wrap;
                border:0.5px solid var(--line); background:var(--beige);
                padding:18px 20px; margin-bottom:26px; }
    button { font:inherit; font-weight:700; font-size:12px; letter-spacing:0.08em;
             text-transform:uppercase; padding:13px 22px; border:0.5px solid var(--ink);
             background:var(--ink); color:var(--cream); cursor:pointer; }
    button:disabled { opacity:0.4; cursor:default; }
    input { width:64px; font:inherit; padding:10px; border:0.5px solid var(--line);
            background:#fff; text-align:right; }
    .tally { font-size:14px; color:var(--muted); }
    .tally b { color:var(--ink); }
    .tally .busy { color:var(--amber-ink); }
    .legend { font-size:12px; color:var(--faint); margin:0 0 12px; }
    .dot { display:inline-block; width:10px; height:10px; border-radius:2px;
           margin:0 4px 0 14px; vertical-align:middle; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(52px,1fr));
            gap:8px; }
    .tile { aspect-ratio:1; border:0.5px solid var(--line); display:flex;
            align-items:center; justify-content:center; font-size:13px;
            font-weight:600; background:#fff; color:var(--muted); }
    .tile.processing { background:var(--amber); color:var(--amber-ink); border-color:var(--amber); }
    .tile.done { background:var(--green-bg); color:var(--green-ink); border-color:var(--green-bg); }
    .tile.error { background:var(--red); color:#fff; border-color:var(--red); }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Queue monitor</h1>
    <div class="sub">Live view of the scoring queue. Fire a burst and watch the system
      take on only what it can, score a couple at a time, and turn the rest away.</div>

    <div class="cards">
      <div class="card"><div class="n" id="c_cap">-</div><div class="l">Capacity</div></div>
      <div class="card hot"><div class="n" id="c_run">-</div><div class="l">Scoring now</div></div>
      <div class="card"><div class="n" id="c_wait">-</div><div class="l">Waiting</div></div>
      <div class="card free"><div class="n" id="c_free">-</div><div class="l">Free slots</div></div>
      <div class="card"><div class="n" id="c_done">-</div><div class="l">Done</div></div>
      <div class="card"><div class="n" id="c_fail">-</div><div class="l">Failed</div></div>
    </div>

    <div class="controls">
      <span class="tally">Send</span>
      <input id="count" type="number" value="20" min="1" max="200">
      <span class="tally">requests</span>
      <button id="fire" onclick="burst()">Send burst</button>
      <div class="tally" id="tally"></div>
    </div>

    <div class="legend">
      <span class="dot" style="background:#fff;border:0.5px solid var(--line)"></span>queued
      <span class="dot" style="background:var(--amber)"></span>scoring
      <span class="dot" style="background:var(--green-bg)"></span>done
      <span class="dot" style="background:var(--red)"></span>error
    </div>
    <div class="grid" id="grid"></div>
  </div>

  <script>
    const SAMPLE = "Agent: Thank you for calling HomeNet support, how can I help?\\n" +
      "Client: I was charged twice this month and I want it fixed.\\n" +
      "Agent: I'm sorry about that. Let me pull up your account.\\n" +
      "Agent: I can see the duplicate charge. I've refunded it now.\\n" +
      "Client: Alright, thank you.";

    async function refresh() {
      try {
        const s = await (await fetch('/jobs')).json();
        document.getElementById('c_cap').textContent = s.capacity;
        document.getElementById('c_run').textContent = s.running;
        document.getElementById('c_wait').textContent = s.waiting;
        document.getElementById('c_free').textContent = s.free_slots;
        document.getElementById('c_done').textContent = s.done;
        document.getElementById('c_fail').textContent = s.failed;
        const recent = s.jobs.slice(-80);
        document.getElementById('grid').innerHTML = recent.map(j =>
          `<div class="tile ${j.status}" title="${j.status}">${j.number}</div>`).join('');
      } catch (e) {}
    }

    async function burst() {
      const btn = document.getElementById('fire');
      const n = Math.max(1, Math.min(200, parseInt(document.getElementById('count').value) || 20));
      btn.disabled = true;
      let accepted = 0, busy = 0, other = 0;
      await Promise.all([...Array(n)].map(async () => {
        try {
          const r = await fetch('/jobs', { method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ transcript: SAMPLE }) });
          if (r.status === 200) accepted++;
          else if (r.status === 503) busy++;
          else other++;
        } catch (e) { other++; }
      }));
      document.getElementById('tally').innerHTML =
        `Sent ${n}: <b>${accepted} accepted</b>, <span class="busy">${busy} busy</span>` +
        (other ? `, ${other} other` : '');
      btn.disabled = false;
      refresh();
    }

    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


@app.get("/weights")
def get_weights():
    """Return the weights currently in effect (saved file, or defaults)."""
    return load_weights()


@app.post("/weights")
def set_weights(payload: dict):
    """Save weights sent from the frontend and return what was stored.

    The body is the key-value pairs, e.g.:
        {"agent": 0.45, "accuracy": 0.20, "compliance": 0.20,
         "conversation": 0.10, "response_time": 0.05}
    save_weights() keeps only known numeric keys, so a bad payload can't
    corrupt the file. Every future call to /analyze then uses these.
    """
    saved = save_weights(payload)
    return {"status": "saved", "weights": saved}


@app.post("/report")
def report(payload: dict):
    """Return a one-call QA report as a downloadable PDF.

    Accepts either a raw transcript (which is scored first) or an already
    computed /analyze result (which is just rendered). The frontend sends the
    result it already has, so no call is scored twice.
    """
    if "final" not in payload and "transcript" in payload:
        transcript, times = parse_transcript(payload["transcript"])
        if not transcript:
            return {"error": "No transcript lines found. Use 'Agent: ...' and "
                             "'Client: ...' on separate lines."}
        payload = run_pipeline(transcript, times)

    pdf = build_report(payload)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition":
                 "attachment; filename=call_qa_report.pdf"},
    )


SAMPLE = """[00:00] Agent: Thank you for calling HomeNet support, how can I help you today?
[00:06] Client: I was charged twice for my subscription this month and I want it fixed.
[00:09] Agent: I'm sorry to hear that. Let me pull up your account and take a look.
[00:14] Client: This is the second time this has happened, it's really frustrating.
[00:31] Agent: I completely understand, that's not acceptable. I can see the duplicate charge now.
[00:36] Client: Okay, so what happens now?
[00:39] Agent: I've refunded the extra charge and it will show up in 3 to 5 business days.
[00:43] Client: Alright, thank you.
[01:09] Agent: Of course. Is there anything else I can help you with?"""


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>SignalQA</title>
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
      <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;1,400&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
      <style>
        :root {
          --cream: #fbf9f4;
          --beige: #eae8e3;
          --beige-warm: #f0e0ca;
          --ink: #1b1c19;
          --muted: #444748;
          --faint: #747878;
          --line: #c4c7c7;
          --error: #ba1a1a;
        }
        * { box-sizing: border-box; }
        body {
          margin: 0;
          font-family: 'Hanken Grotesk', -apple-system, sans-serif;
          background: var(--cream);
          color: var(--ink);
          -webkit-font-smoothing: antialiased;
        }
        .serif { font-family: 'Playfair Display', Georgia, serif; }
        a { color: inherit; text-decoration: none; }

        /* ---- top nav ---- */
        .nav {
          display: flex; align-items: center; justify-content: space-between;
          padding: 26px 64px; border-bottom: 0.5px solid var(--line);
        }
        .wordmark { font-family: 'Playfair Display', serif; font-style: italic; font-size: 22px; letter-spacing: 0.02em; }

        /* ---- layout ---- */
        .wrap { max-width: 1440px; margin: 0 auto; padding: 0 64px; }
        .grid { display: grid; grid-template-columns: 360px 1fr; gap: 72px; padding: 56px 0 96px; }
        @media (max-width: 900px) { .wrap { padding: 0 24px; } .grid { grid-template-columns: 1fr; gap: 48px; } .nav { padding: 20px 24px; } }

        h1.title { font-family: 'Playfair Display', serif; font-weight: 400; font-size: 56px; line-height: 1.05; letter-spacing: -0.02em; margin: 0 0 18px; }
        @media (max-width: 900px) { h1.title { font-size: 40px; } }
        .lede { font-size: 15px; line-height: 1.65; color: var(--muted); margin: 0 0 40px; max-width: 34ch; }

        .label { font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); }

        /* ---- input ---- */
        .field-label { display: block; margin-bottom: 12px; }
        textarea {
          width: 100%; min-height: 300px; background: var(--cream);
          border: 0.5px solid var(--line); border-radius: 0; padding: 18px;
          font-family: 'Hanken Grotesk', sans-serif; font-size: 14px; line-height: 1.7;
          color: var(--ink); resize: vertical;
        }
        textarea::placeholder { color: var(--faint); }
        textarea:focus { outline: none; border-color: var(--ink); }
        .actions { display: flex; gap: 14px; margin-top: 22px; }
        .btn {
          font-family: 'Hanken Grotesk', sans-serif; font-size: 12px; font-weight: 700;
          letter-spacing: 0.1em; text-transform: uppercase; padding: 15px 26px;
          border-radius: 0; cursor: pointer; border: 0.5px solid var(--ink); transition: background .15s, color .15s;
        }
        .btn.primary { background: var(--ink); color: var(--cream); }
        .btn.primary:hover { background: var(--beige-warm); color: var(--ink); border-color: var(--beige-warm); }
        .btn.ghost { background: transparent; color: var(--ink); }
        .btn.ghost:hover { background: var(--beige); }
        .btn:disabled { opacity: 0.4; cursor: default; }
        .hint { font-size: 12px; color: var(--faint); margin-top: 18px; line-height: 1.5; }

        /* ---- weights editor ---- */
        .wrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 0.5px solid var(--line); }
        .wrow label { font-size: 14px; }
        .wcell { display: flex; align-items: center; gap: 6px; }
        .wcell input {
          width: 62px; background: var(--cream); border: 0.5px solid var(--line);
          padding: 8px 10px; font-family: 'Hanken Grotesk', sans-serif; font-size: 14px;
          color: var(--ink); text-align: right;
        }
        .wcell input:focus { outline: none; border-color: var(--ink); }
        .wsuffix { font-size: 13px; color: var(--faint); }
        .wtotal { border-bottom: none; }
        .wtotal label { font-weight: 600; }
        .wtotal #w_total { font-size: 15px; }
        .wtotal.off #w_total { color: var(--error); }
        .wtotal.off label { color: var(--error); }

        /* ---- left: tense moments ---- */
        .side-block { margin-top: 64px; }
        .side-block > .label { display: block; margin-bottom: 22px; padding-bottom: 12px; border-bottom: 0.5px solid var(--line); }
        .tense-item { padding-left: 16px; border-left: 2px solid var(--error); margin-bottom: 22px; }
        .tense-item .who { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--error); }
        .tense-item .val { font-size: 14px; color: var(--muted); margin-top: 2px; }

        /* ---- right column ---- */
        #results { display: none; }
        .placeholder { color: var(--faint); font-size: 15px; line-height: 1.7; max-width: 40ch; padding-top: 8px; }

        .score-block { display: flex; gap: 48px; align-items: center; flex-wrap: wrap; }
        .ring-wrap { position: relative; width: 200px; height: 200px; flex: none; }
        .ring-wrap svg { width: 200px; height: 200px; }
        .ring-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .ring-num { font-family: 'Playfair Display', serif; font-size: 30px; }
        .ring-label { font-size: 10px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--faint); margin-top: 4px; }
        .subscores { display: grid; grid-template-columns: 1fr 1fr; gap: 30px 44px; }
        .sub .sub-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); }
        .sub .sub-num { font-family: 'Playfair Display', serif; font-size: 34px; line-height: 1.1; margin-top: 6px; }

        .warn { background: var(--beige-warm); border: 0.5px solid #d8c49a; color: #6b4e12; padding: 14px 18px; margin-top: 32px; font-size: 14px; }

        section.blk { margin-top: 56px; }
        section.blk > h2 {
          font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;
          color: var(--faint); margin: 0 0 20px; padding-bottom: 12px; border-bottom: 0.5px solid var(--line);
        }
        .prose { font-size: 16px; line-height: 1.7; color: var(--ink); white-space: pre-wrap; }

        /* compliance / scorecard rows */
        .fill { background: var(--beige); padding: 30px 34px; }
        .row-line { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 0; border-bottom: 0.5px solid var(--line); }
        .row-line:last-child { border-bottom: none; }
        .row-line .rl-text { font-size: 15px; }
        .tag { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 5px 12px; color: #fff; }
        .tag.ok { background: var(--ink); }
        .tag.broken, .tag.fail { background: var(--error); }
        .tag.partial { background: var(--secondary, #685d4b); background: #685d4b; }
        .tag.pass { background: var(--ink); }
        .tag.unrated { background: var(--faint); }
        .evidence { font-size: 13px; font-style: italic; color: var(--error); margin-top: 4px; }
        .rl-sub { font-size: 13px; color: var(--muted); margin-top: 4px; }

        /* accuracy two-box */
        .acc-item { margin-bottom: 40px; }
        .acc-item:last-child { margin-bottom: 0; }
        .acc-q { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
        .acc-meta { font-size: 12px; color: var(--faint); margin-bottom: 16px; }
        .acc-boxes { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        @media (max-width: 700px) { .acc-boxes { grid-template-columns: 1fr; } }
        .acc-box { padding: 22px 24px; border: 0.5px solid var(--line); }
        .acc-box.ideal { background: var(--beige-warm); border-color: var(--beige-warm); }
        .acc-box .box-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); margin-bottom: 12px; }
        .acc-box .box-text { font-size: 14px; line-height: 1.6; font-style: italic; }
        .kp { font-size: 13px; margin-top: 12px; }
        .kp.ok { color: #3d5c46; } .kp.no { color: var(--error); }

        /* response time */
        .rt-row { display: flex; align-items: baseline; gap: 18px; padding: 12px 0; border-bottom: 0.5px solid var(--line); }
        .rt-row:last-child { border-bottom: none; }
        .rt-delay { font-family: 'Playfair Display', serif; font-size: 20px; min-width: 64px; }
        .rt-delay.slow { color: var(--error); }
        .rt-text { font-size: 14px; color: var(--muted); }

        /* suggestions */
        .sugg { font-size: 15px; line-height: 1.7; color: var(--ink); white-space: pre-wrap; }

        .spinner { width: 14px; height: 14px; border: 2px solid var(--line); border-top-color: var(--ink); border-radius: 50%; animation: spin .8s linear infinite; display: inline-block; vertical-align: middle; margin-right: 6px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        footer { border-top: 0.5px solid var(--line); }
        .foot { max-width: 1440px; margin: 0 auto; padding: 40px 64px; display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap; }
        .foot .copy { font-size: 12px; color: var(--faint); max-width: 30ch; line-height: 1.6; }
      </style>
    </head>
    <body>
      <nav class="nav">
        <div class="wordmark">SignalQA</div>
      </nav>

      <div class="wrap">
        <div class="grid">
          <div class="left">
            <h1 class="title">SignalQA</h1>
            <p class="lede">Automated linguistic and compliance evaluation for telecommunication customer interactions. Precision auditing for quality control.</p>

            <label class="label field-label">Session Transcript Input</label>
            <textarea id="transcript" placeholder="Paste call transcript here or load sample for analysis..."></textarea>
            <div class="actions">
              <button class="btn primary" id="analyzeBtn" onclick="analyze()">Analyze Call</button>
              <button class="btn ghost" onclick="loadSample()">Load Sample</button>
              <button class="btn ghost" id="reportBtn" onclick="downloadReport()" style="display:none">Download Report</button>
            </div>
            <div class="hint" id="status">One line per turn. Works with Agent:/Client:, also AI:/Customer: and [00:15] timestamps.</div>

            <div class="side-block" id="weightsBlock">
              <span class="label">Scoring Weights</span>
              <div class="wrow"><label>Agent handling</label><span class="wcell"><input type="number" id="w_agent" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Answer accuracy</label><span class="wcell"><input type="number" id="w_accuracy" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Compliance</label><span class="wcell"><input type="number" id="w_compliance" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Customer sentiment</label><span class="wcell"><input type="number" id="w_conversation" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Response time</label><span class="wcell"><input type="number" id="w_response_time" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow wtotal"><label>Total</label><span class="wcell"><strong id="w_total">100</strong><span class="wsuffix">%</span></span></div>
              <div class="actions">
                <button class="btn primary" id="saveWeightsBtn" onclick="saveWeights()">Save Weights</button>
                <button class="btn ghost" onclick="loadWeights()">Reload</button>
              </div>
              <div class="hint" id="weightsStatus">Loading current weights…</div>
            </div>

            <div class="side-block" id="tenseBlock" style="display:none">
              <span class="label">Tense Moment Detected</span>
              <div id="tense"></div>
            </div>
          </div>

          <div class="right">
            <div id="placeholder" class="placeholder">Run an analysis to see the quality report — final score, agent scorecard, compliance check, answer accuracy, response time, and suggestions.</div>

            <div id="results">
              <div class="score-block">
                <div class="ring-wrap">
                  <svg viewBox="0 0 200 200">
                    <circle cx="100" cy="100" r="88" fill="none" stroke="var(--line)" stroke-width="2"/>
                    <circle id="ringArc" cx="100" cy="100" r="88" fill="none" stroke="var(--ink)" stroke-width="2" stroke-dasharray="552.9" stroke-dashoffset="552.9" transform="rotate(-90 100 100)"/>
                  </svg>
                  <div class="ring-center">
                    <div class="ring-num serif" id="finalScore">&mdash;</div>
                    <div class="ring-label">Final QA Score</div>
                  </div>
                </div>
                <div class="subscores">
                  <div class="sub"><div class="sub-label">Agent</div><div class="sub-num" id="agentScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Conversation</div><div class="sub-num" id="convScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Accuracy</div><div class="sub-num" id="accScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Compliance</div><div class="sub-num" id="compScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Response Time</div><div class="sub-num" id="rtScore">&mdash;</div></div>
                </div>
              </div>

              <div class="warn" id="warning" style="display:none"></div>

              <section class="blk"><h2>Summary</h2><div class="prose" id="summary"></div></section>
              <section class="blk"><h2>Compliance Check</h2><div class="fill" id="compliance"></div></section>
              <section class="blk"><h2>Agent Scorecard</h2><div id="scorecard"></div></section>
              <section class="blk"><h2>Response Time</h2><div id="responsetime"></div></section>
              <section class="blk"><h2>Accuracy Analysis</h2><div id="accuracy"></div></section>
              <section class="blk"><h2>Suggestions</h2><div class="sugg" id="suggestions"></div></section>
              <section class="blk"><h2>Gemma Token Cost</h2><div id="tokencost"></div></section>
            </div>
          </div>
        </div>
      </div>

      <footer>
        <div class="foot">
          <div class="wordmark">SignalQA</div>
          <div class="copy">Automated linguistic and compliance evaluation. Defined by precision.</div>
        </div>
      </footer>

      <script>
        const SAMPLE = %SAMPLE%;
        function loadSample() { document.getElementById('transcript').value = SAMPLE; }
        function esc(s){ const d=document.createElement('div'); d.textContent = (s==null?'':s); return d.innerHTML; }

        // ---- scoring weights ----
        // The backend stores weights as fractions (0.45); we show them as whole
        // percentages (45) because that's how people read them. We convert on
        // the way in and out. The scorer rescales anyway, so they need not total
        // exactly 100 — but we show the running total so it's easy to keep tidy.
        const WEIGHT_KEYS = ['agent','accuracy','compliance','conversation','response_time'];

        function updateTotal() {
          var total = 0;
          WEIGHT_KEYS.forEach(function(k){ total += parseFloat(document.getElementById('w_'+k).value) || 0; });
          total = Math.round(total);
          document.getElementById('w_total').textContent = total;
          // Flag when it doesn't add to 100. The score still rescales, so this
          // is a nudge to keep it tidy, not a hard error.
          document.querySelector('.wtotal').classList.toggle('off', total !== 100);
        }

        async function loadWeights() {
          const st = document.getElementById('weightsStatus');
          try {
            const w = await (await fetch('/weights')).json();
            WEIGHT_KEYS.forEach(function(k){
              document.getElementById('w_'+k).value = Math.round((w[k]||0) * 100);
            });
            updateTotal();
            st.textContent = 'These weights are applied to every call.';
          } catch(e){ st.textContent = 'Could not load weights: ' + e; }
        }

        async function saveWeights() {
          const st = document.getElementById('weightsStatus');
          const btn = document.getElementById('saveWeightsBtn');
          const payload = {};
          WEIGHT_KEYS.forEach(function(k){
            payload[k] = (parseFloat(document.getElementById('w_'+k).value) || 0) / 100;
          });
          btn.disabled = true;
          st.textContent = 'Saving…';
          try {
            const res = await fetch('/weights', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
            await res.json();
            st.textContent = 'Saved. Every call from now on uses these weights.';
          } catch(e){ st.textContent = 'Could not save: ' + e; }
          btn.disabled = false;
        }

        // Recompute the total live as the numbers are edited.
        WEIGHT_KEYS.forEach(function(k){
          document.getElementById('w_'+k).addEventListener('input', updateTotal);
        });

        loadWeights();  // fill the boxes with the current weights on page load

        let lastResult = null;  // the most recent /analyze result, for the PDF

        async function downloadReport() {
          if (!lastResult) return;
          const rbtn = document.getElementById('reportBtn');
          const status = document.getElementById('status');
          rbtn.disabled = true;
          const original = rbtn.textContent;
          rbtn.textContent = 'Preparing…';
          try {
            const res = await fetch('/report', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(lastResult) });
            if (!res.ok) { status.textContent = 'Could not build the report.'; return; }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'call_qa_report.pdf';
            document.body.appendChild(a); a.click(); a.remove();
            URL.revokeObjectURL(url);
          } catch(e){ status.textContent = 'Something went wrong: ' + e; }
          rbtn.textContent = original;
          rbtn.disabled = false;
        }

        async function analyze() {
          const transcript = document.getElementById('transcript').value.trim();
          const btn = document.getElementById('analyzeBtn');
          const status = document.getElementById('status');
          if (!transcript) { status.textContent = 'Please paste a transcript first.'; return; }
          btn.disabled = true;
          status.innerHTML = '<span class="spinner"></span> Analyzing…';
          try {
            const res = await fetch('/analyze', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ transcript }) });
            const data = await res.json();
            if (data.error) { status.textContent = data.error; btn.disabled=false; return; }
            render(data);
            lastResult = data;
            document.getElementById('reportBtn').style.display = '';
            status.textContent = 'Analysis complete.';
          } catch(e){ status.textContent = 'Something went wrong: ' + e; }
          btn.disabled = false;
        }

        function render(d) {
          document.getElementById('placeholder').style.display = 'none';
          document.getElementById('results').style.display = 'block';

          document.getElementById('finalScore').textContent = d.final;
          const C = 552.9;
          document.getElementById('ringArc').style.strokeDashoffset = C * (1 - Math.max(0, Math.min(100, d.final)) / 100);

          document.getElementById('agentScore').textContent = d.agent;
          document.getElementById('convScore').textContent = d.conversation;
          document.getElementById('accScore').textContent = (d.accuracy_overall==null)?'n/a':d.accuracy_overall;
          document.getElementById('compScore').textContent = (d.compliance_score==null)?'n/a':d.compliance_score;
          document.getElementById('rtScore').textContent = (d.response_time_score==null)?'n/a':d.response_time_score;

          document.getElementById('summary').textContent = d.summary;
          document.getElementById('suggestions').innerHTML =
            (d.suggestions||[]).map(function(s){ return '<div class="sugg-item">'+esc(s)+'</div>'; }).join('');

          const warn = document.getElementById('warning');
          if (d.warning) { warn.textContent = d.warning; warn.style.display='block'; } else { warn.style.display='none'; }

          document.getElementById('compliance').innerHTML = (d.compliance||[]).map(function(r){
            var broken = r.status === 'BROKEN';
            return '<div class="row-line"><div><div class="rl-text">'+esc(r.rule)+'</div>'+(broken?'<div class="evidence">heard: "'+esc(r.evidence)+'"</div>':'')+'</div><span class="tag '+(broken?'broken':'ok')+'">'+(broken?'Broken':'OK')+'</span></div>';
          }).join('');

          document.getElementById('scorecard').innerHTML = (d.ratings||[]).map(function(r){
            return '<div class="row-line"><div><div class="rl-text">'+esc(r.name)+'</div><div class="rl-sub">'+esc(r.reason)+'</div></div><span class="tag '+r.rating.toLowerCase()+'">'+esc(r.rating)+'</span></div>';
          }).join('');

          var rt = document.getElementById('responsetime');
          if (!d.response_times || d.response_times.length===0) {
            rt.innerHTML = '<div class="placeholder">No timestamps found &mdash; add times like [00:15] to each line to measure response time.</div>';
          } else {
            rt.innerHTML = d.response_times.map(function(r){
              return '<div class="rt-row"><span class="rt-delay serif '+(r.slow?'slow':'')+'">'+r.delay+'s</span><span class="rt-text">after: '+esc(r.client_text)+'</span></div>';
            }).join('');
          }

          var acc = document.getElementById('accuracy');
          if (!d.accuracy || d.accuracy.length===0) {
            acc.innerHTML = '<div class="placeholder">No client questions matched the knowledge base, so accuracy could not be checked.</div>';
          } else {
            acc.innerHTML = d.accuracy.map(function(a){
              var covered = (a.covered||[]).map(function(p){return '<div class="kp ok">✓ '+esc(p)+'</div>';}).join('');
              var missed = (a.missed||[]).map(function(p){return '<div class="kp no">✗ '+esc(p)+'</div>';}).join('');
              return '<div class="acc-item"><div class="acc-q">'+esc(a.client_question)+'</div><div class="acc-meta">matched: '+esc(a.matched_question)+' · '+esc(a.confidence)+' · '+a.accuracy+'/100</div><div class="acc-boxes"><div class="acc-box"><div class="box-label">Analyst Transcript</div><div class="box-text">"'+esc(a.agent_answer)+'"</div></div><div class="acc-box ideal"><div class="box-label">Ideal Answer</div><div class="box-text">"'+esc(a.ideal_answer)+'"</div></div></div>'+covered+missed+'</div>';
            }).join('');
          }

          var tok = document.getElementById('tokencost');
          var u = d.token_usage;
          if (!u) {
            tok.innerHTML = '<div class="placeholder">No token data available.</div>';
          } else {
            var rows = (u.calls||[]).map(function(c){
              return '<div class="row-line"><div class="rl-text">'+esc(c.label)+'</div><div class="rl-sub">'+c.input+' in · '+c.output+' out · '+(c.input+c.output)+' total</div></div>';
            }).join('');
            rows += '<div class="row-line"><div class="rl-text">Total</div><div class="rl-sub">'+u.input+' in · '+u.output+' out · <strong>'+u.total+' tokens</strong></div></div>';
            tok.innerHTML = rows + '<div class="acc-meta">Gemma only — sentiment and rule/accuracy checks run locally with no tokens.</div>';
          }

          var tenseBlock = document.getElementById('tenseBlock');
          var tense = document.getElementById('tense');
          tenseBlock.style.display = 'block';
          if (!d.intense || d.intense.length===0) {
            tense.innerHTML = '<div class="placeholder">None &mdash; the call stayed calm.</div>';
          } else {
            tense.innerHTML = d.intense.map(function(m){
              return '<div class="tense-item"><div class="who">Turn '+m.turn+': '+esc(m.speaker)+'</div><div class="val">sentiment '+m.sentiment+'</div></div>';
            }).join('');
          }
        }
      </script>
    </body>
    </html>
    """.replace("%SAMPLE%", _sample_json())


def _sample_json():
    import json
    return json.dumps(SAMPLE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
