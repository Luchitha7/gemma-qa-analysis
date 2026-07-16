"""WEB VERSION of the QA analysis.

Paste a call transcript in the browser, click Analyze, and get the full styled
QA report (final score, agent scorecard, summary, tense moments, suggestions).

It reuses the exact same pipeline as qa_report.py -- nothing new is analysed
here, it's just a web front-end over the parts we already built.

    python web_app.py
    # then open http://localhost:8000

Requires Ollama running ('brew services start ollama') and the venv active.
"""

import html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from gemma_client import gemma
from qa_intensity import analyze
from qa_agent import (
    AGENT_WEIGHT, CONVERSATION_WEIGHT, RATING_SCORES,
    build_prompt, conversation_score, parse_ratings,
)
from qa_summary import SUMMARY_PROMPT
from qa_suggestions import SUGGESTIONS_PROMPT, clean_suggestions

app = FastAPI()


class TranscriptIn(BaseModel):
    transcript: str


def parse_transcript(raw):
    """Turn pasted text into [(speaker, text), ...].

    Accepts lines like 'Agent: hello' or 'Client: hi'. Any line without a
    recognised speaker is attached to the previous line (so a wrapped sentence
    still works). Unknown speakers are kept as-is.
    """
    turns = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            speaker, text = line.split(":", 1)
            speaker, text = speaker.strip(), text.strip()
            if speaker and len(speaker) <= 20 and text:
                turns.append((speaker, text))
                continue
        # no clear speaker -> tack onto the previous turn
        if turns:
            prev_speaker, prev_text = turns[-1]
            turns[-1] = (prev_speaker, f"{prev_text} {line}".strip())
    return turns


def band(score):
    if score >= 80:
        return "GOOD"
    if score >= 60:
        return "OKAY"
    return "NEEDS IMPROVEMENT"


def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


def run_pipeline(transcript):
    """Same steps as qa_report.py, returned as a dict for the web page."""
    transcript_text = format_transcript(transcript)

    # RoBERTa: sentiment + tense moments
    rows = analyze(transcript)
    intense = [r for r in rows if r["intense"]]

    # Gemma: three small calls
    summary = gemma(SUMMARY_PROMPT.format(transcript=transcript_text))
    ratings = parse_ratings(gemma(build_prompt(transcript_text, intense)))
    suggestions = clean_suggestions(gemma(SUGGESTIONS_PROMPT.format(transcript=transcript_text)))

    # Scores
    rated = [RATING_SCORES[r["rating"]] for r in ratings if r["rating"]]
    agent = round(sum(rated) / len(rated), 1) if rated else 0.0
    conv = conversation_score(rows)
    final = round(agent * AGENT_WEIGHT + conv * CONVERSATION_WEIGHT, 1)

    return {
        "final": final,
        "agent": agent,
        "conversation": conv,
        "band": band(final),
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
        "suggestions": suggestions,
    }


@app.post("/analyze")
def analyze_call(payload: TranscriptIn):
    transcript = parse_transcript(payload.transcript)
    if not transcript:
        return {"error": "No transcript lines found. Use 'Agent: ...' and "
                         "'Client: ...' on separate lines."}
    return run_pipeline(transcript)


SAMPLE = """Agent: Thank you for calling support, how can I help you today?
Client: I was charged twice for my subscription this month and I want it fixed.
Agent: I'm sorry to hear that. Let me pull up your account and take a look.
Client: This is the second time this has happened, it's really frustrating.
Agent: I completely understand, that's not acceptable. I can see the duplicate charge now.
Agent: I've refunded the extra charge and it will show up in 3 to 5 business days.
Client: Okay, thank you. I appreciate you sorting it out quickly.
Agent: Of course. Is there anything else I can help you with?
Client: No that's all, thanks for your help."""


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
    <head>
      <title>Call QA Analysis</title>
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
      <style>
        * { box-sizing: border-box; }
        body {
          margin: 0;
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
          background-color: #f3f2ef;
          background-image: radial-gradient(circle at 12% 8%, #ffffff 0%, rgba(255,255,255,0) 45%),
                             radial-gradient(circle at 92% 90%, #eae7e0 0%, rgba(234,231,224,0) 50%);
          min-height: 100vh;
          color: #23252b;
        }
        .page { min-height: 100vh; padding: 56px 24px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 820px; }
        h1 { font-size: 28px; font-weight: 800; color: #14151a; margin: 0 0 6px; letter-spacing: -0.02em; }
        .subtitle { color: #70747e; font-size: 15px; margin: 0 0 28px; }
        .panel {
          background: #ffffff; border: 1px solid #e6e7eb; border-radius: 16px;
          padding: 24px 28px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(20,21,26,0.04);
        }
        .panel h2 {
          font-size: 12px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.08em; color: #9a9ea8; margin: 0 0 14px;
        }
        textarea {
          width: 100%; min-height: 200px; border: 1px solid #e6e7eb; border-radius: 12px;
          padding: 14px 16px; font-family: 'Inter', sans-serif; font-size: 14px;
          line-height: 1.6; resize: vertical; color: #23252b;
        }
        textarea:focus { outline: none; border-color: #14151a; }
        .row { display: flex; gap: 12px; align-items: center; margin-top: 14px; }
        .btn {
          font-family: inherit; font-size: 14px; font-weight: 700; padding: 11px 26px;
          border-radius: 999px; border: none; cursor: pointer; background: #14151a; color: #fff;
        }
        .btn:disabled { opacity: 0.5; cursor: default; }
        .btn.ghost { background: #f0f1f4; color: #5c606a; }
        .hint { font-size: 13px; color: #9a9ea8; }
        .score-hero { text-align: center; }
        .score-value { font-size: 54px; font-weight: 800; letter-spacing: -0.02em; }
        .score-value.good { color: #22a06b; }
        .score-value.okay { color: #d99100; }
        .score-value.bad { color: #dc4444; }
        .score-band { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }
        .subscores { display: flex; justify-content: center; gap: 40px; margin-top: 18px; }
        .subscore { text-align: center; }
        .subscore .n { font-size: 22px; font-weight: 800; color: #14151a; }
        .subscore .l { font-size: 12px; color: #9a9ea8; margin-top: 2px; }
        .scorecard-row {
          display: flex; align-items: center; gap: 14px; padding: 12px 0;
          border-bottom: 1px solid #f0f1f4;
        }
        .scorecard-row:last-child { border-bottom: none; }
        .pill {
          font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
          padding: 4px 10px; border-radius: 6px; min-width: 66px; text-align: center;
        }
        .pill.pass { background: #22a06b; color: #fff; }
        .pill.partial { background: #f2a900; color: #fff; }
        .pill.fail { background: #dc4444; color: #fff; }
        .pill.unrated { background: #eceef1; color: #5c606a; }
        .sc-name { font-weight: 700; font-size: 15px; min-width: 150px; }
        .sc-reason { font-size: 14px; color: #5c606a; }
        .tense {
          border-left: 3px solid #dc4444; background: #fdf4f4; border-radius: 6px;
          padding: 10px 14px; margin-bottom: 10px;
        }
        .tense .meta { font-size: 12px; color: #c62828; font-weight: 700; margin-bottom: 4px; }
        .tense .txt { font-size: 14px; color: #23252b; }
        .prose { font-size: 15px; line-height: 1.65; color: #23252b; white-space: pre-wrap; }
        .empty { color: #9a9ea8; font-size: 14px; }
        .spinner {
          width: 18px; height: 18px; border: 3px solid #d9dbe0; border-top-color: #14151a;
          border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        #results { display: none; }
      </style>
    </head>
    <body>
      <div class="page">
      <div class="container">
        <h1>Call QA Analysis</h1>
        <p class="subtitle">Paste a call transcript and get an automated quality report — RoBERTa + Gemma, all local.</p>

        <div class="panel">
          <h2>Transcript</h2>
          <textarea id="transcript" placeholder="Agent: Thank you for calling support...&#10;Client: I have a problem with my bill...&#10;Agent: ..."></textarea>
          <div class="row">
            <button class="btn" id="analyzeBtn" onclick="analyze()">Analyze Call</button>
            <button class="btn ghost" onclick="loadSample()">Load sample</button>
            <span class="hint" id="status">One line per turn, starting with "Agent:" or "Client:".</span>
          </div>
        </div>

        <div id="results">
          <div class="panel score-hero">
            <h2>Final QA Score</h2>
            <div class="score-value" id="finalScore">—</div>
            <div class="score-band" id="finalBand"></div>
            <div class="subscores">
              <div class="subscore"><div class="n" id="agentScore">—</div><div class="l">Agent</div></div>
              <div class="subscore"><div class="n" id="convScore">—</div><div class="l">Conversation</div></div>
            </div>
          </div>

          <div class="panel">
            <h2>Summary</h2>
            <div class="prose" id="summary"></div>
          </div>

          <div class="panel">
            <h2>Agent Scorecard</h2>
            <div id="scorecard"></div>
          </div>

          <div class="panel">
            <h2>Tense Moments</h2>
            <div id="tense"></div>
          </div>

          <div class="panel">
            <h2>Suggestions</h2>
            <div class="prose" id="suggestions"></div>
          </div>
        </div>
      </div>
      </div>

      <script>
        const SAMPLE = %SAMPLE%;

        function loadSample() {
          document.getElementById('transcript').value = SAMPLE;
        }

        function esc(s) {
          const d = document.createElement('div');
          d.textContent = s;
          return d.innerHTML;
        }

        async function analyze() {
          const transcript = document.getElementById('transcript').value.trim();
          const btn = document.getElementById('analyzeBtn');
          const status = document.getElementById('status');
          if (!transcript) { status.textContent = 'Please paste a transcript first.'; return; }

          btn.disabled = true;
          status.innerHTML = '<span class="spinner"></span> Analyzing… (this takes a few seconds)';

          try {
            const res = await fetch('/analyze', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ transcript })
            });
            const data = await res.json();
            if (data.error) { status.textContent = data.error; btn.disabled = false; return; }
            render(data);
            status.textContent = 'Done.';
          } catch (e) {
            status.textContent = 'Something went wrong: ' + e;
          }
          btn.disabled = false;
        }

        function render(d) {
          const cls = d.final >= 80 ? 'good' : (d.final >= 60 ? 'okay' : 'bad');
          const fs = document.getElementById('finalScore');
          fs.textContent = d.final;
          fs.className = 'score-value ' + cls;
          document.getElementById('finalBand').textContent = d.band;
          document.getElementById('agentScore').textContent = d.agent;
          document.getElementById('convScore').textContent = d.conversation;
          document.getElementById('summary').textContent = d.summary;
          document.getElementById('suggestions').textContent = d.suggestions;

          document.getElementById('scorecard').innerHTML = d.ratings.map(r => `
            <div class="scorecard-row">
              <span class="pill ${r.rating.toLowerCase()}">${r.rating}</span>
              <span class="sc-name">${esc(r.name)}</span>
              <span class="sc-reason">${esc(r.reason)}</span>
            </div>`).join('');

          const tense = document.getElementById('tense');
          if (d.intense.length === 0) {
            tense.innerHTML = '<div class="empty">None — the call stayed calm.</div>';
          } else {
            tense.innerHTML = d.intense.map(m => `
              <div class="tense">
                <div class="meta">Turn ${m.turn} · ${esc(m.speaker)} · sentiment ${m.sentiment}</div>
                <div class="txt">${esc(m.text)}</div>
              </div>`).join('');
          }

          document.getElementById('results').style.display = 'block';
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
