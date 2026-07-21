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

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from gemma_client import gemma
from qa_intensity import analyze
from qa_agent import (
    AGENT_WEIGHT, CONVERSATION_WEIGHT, RATING_SCORES,
    agent_harsh_lines, apply_tone_penalty, build_prompt, conversation_score,
    parse_ratings,
)
from qa_summary import SUMMARY_PROMPT
from qa_suggestions import SUGGESTIONS_PROMPT, clean_suggestions
from rag_accuracy import check_accuracy
from rag_compliance import check_compliance
from response_time import (
    leading_time_seconds, response_delays, response_time_score,
)

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

    # Gemma: three small calls
    harsh = agent_harsh_lines(rows)
    summary = gemma(SUMMARY_PROMPT.format(transcript=transcript_text))
    ratings = apply_tone_penalty(
        parse_ratings(gemma(build_prompt(transcript_text, intense, harsh))), harsh)
    suggestions = clean_suggestions(gemma(SUGGESTIONS_PROMPT.format(transcript=transcript_text)))

    # RAG: how accurate were the agent's answers vs the ideal answers?
    accuracy_results, accuracy_overall = check_accuracy(transcript)
    # RAG: did the agent break any compliance rules? (token-free)
    compliance_results, compliance_score = check_compliance(transcript)
    # Timestamps: how fast did the agent reply? (token-free)
    delays = response_delays(transcript, times)
    rt_score = response_time_score(delays)

    # Scores
    rated = [RATING_SCORES[r["rating"]] for r in ratings if r["rating"]]
    agent = round(sum(rated) / len(rated), 1) if rated else 0.0
    conv = conversation_score(rows)
    final = round(agent * AGENT_WEIGHT + conv * CONVERSATION_WEIGHT, 1)

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
        "suggestions": suggestions,
        "compliance_score": compliance_score,
        "compliance": compliance_results,
        "response_time_score": rt_score,
        "response_times": [
            {
                "agent_turn": d["agent_turn"],
                "delay": d["delay"],
                "slow": d["slow"],
                "client_text": d["client_text"],
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
        .acc-row { padding: 14px 0; border-bottom: 1px solid #f0f1f4; }
        .acc-row:last-child { border-bottom: none; }
        .acc-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 6px; }
        .acc-q { font-weight: 700; font-size: 14px; }
        .acc-score {
          font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 999px; white-space: nowrap;
        }
        .acc-score.high { background: #e3f4ec; color: #1a7a4f; }
        .acc-score.mid  { background: #fdf3e0; color: #8a6100; }
        .acc-score.low  { background: #fdeaea; color: #c62828; }
        .acc-line { font-size: 13px; color: #5c606a; margin-top: 3px; }
        .acc-line b { color: #23252b; font-weight: 600; }
        .kp { font-size: 13px; margin-top: 4px; }
        .kp.ok  { color: #1a7a4f; }
        .kp.no  { color: #c62828; }
        .acc-conf { font-size: 11px; color: #9a9ea8; margin-left: 8px; font-weight: 500; }
        .comp-row { display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f0f1f4; }
        .comp-row:last-child { border-bottom: none; }
        .comp-mark { font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 6px; min-width: 70px; text-align: center; }
        .comp-mark.ok { background: #e3f4ec; color: #1a7a4f; }
        .comp-mark.broken { background: #fdeaea; color: #c62828; }
        .comp-body .rule { font-weight: 600; font-size: 14px; }
        .comp-body .ev { font-size: 13px; color: #c62828; margin-top: 3px; font-style: italic; }
        .rt-row { display: flex; align-items: center; gap: 12px; padding: 9px 0; border-bottom: 1px solid #f0f1f4; }
        .rt-row:last-child { border-bottom: none; }
        .rt-delay { font-size: 13px; font-weight: 700; padding: 3px 10px; border-radius: 999px; min-width: 58px; text-align: center; }
        .rt-delay.ok { background: #e3f4ec; color: #1a7a4f; }
        .rt-delay.slow { background: #fdeaea; color: #c62828; }
        .rt-text { font-size: 13px; color: #5c606a; }
        .parsed-info { font-size: 12px; color: #9a9ea8; margin-top: 12px; }
        .warn {
          background: #fef6e7; border: 1px solid #f4d68a; color: #8a6100;
          border-radius: 12px; padding: 12px 16px; margin-bottom: 20px; font-size: 14px;
        }
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
            <span class="hint" id="status">One line per turn. Works with "Agent:"/"Client:", also "AI:"/"Customer:" and timestamps.</span>
          </div>
        </div>

        <div id="results">
          <div class="warn" id="warning" style="display:none"></div>
          <div class="panel score-hero">
            <h2>Final QA Score</h2>
            <div class="score-value" id="finalScore">—</div>
            <div class="score-band" id="finalBand"></div>
            <div class="subscores">
              <div class="subscore"><div class="n" id="agentScore">—</div><div class="l">Agent</div></div>
              <div class="subscore"><div class="n" id="convScore">—</div><div class="l">Conversation</div></div>
              <div class="subscore"><div class="n" id="accScore">—</div><div class="l">Answer accuracy</div></div>
              <div class="subscore"><div class="n" id="compScore">—</div><div class="l">Compliance</div></div>
              <div class="subscore"><div class="n" id="rtScore">—</div><div class="l">Response time</div></div>
            </div>
            <div class="parsed-info" id="parsedInfo"></div>
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
            <h2>Response Time</h2>
            <div id="responsetime"></div>
          </div>

          <div class="panel">
            <h2>Compliance Check (RAG)</h2>
            <div id="compliance"></div>
          </div>

          <div class="panel">
            <h2>Answer Accuracy (RAG)</h2>
            <div id="accuracy"></div>
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

          const info = document.getElementById('parsedInfo');
          info.textContent = `Read ${d.parsed.turns} turns · ${d.parsed.agent} agent · ${d.parsed.client} client`;

          const warn = document.getElementById('warning');
          if (d.warning) { warn.textContent = '⚠ ' + d.warning; warn.style.display = 'block'; }
          else { warn.style.display = 'none'; }

          document.getElementById('scorecard').innerHTML = d.ratings.map(r => `
            <div class="scorecard-row">
              <span class="pill ${r.rating.toLowerCase()}">${r.rating}</span>
              <span class="sc-name">${esc(r.name)}</span>
              <span class="sc-reason">${esc(r.reason)}</span>
            </div>`).join('');

          document.getElementById('rtScore').textContent =
            (d.response_time_score === undefined || d.response_time_score === null) ? 'n/a' : d.response_time_score;
          const rt = document.getElementById('responsetime');
          if (!d.response_times || d.response_times.length === 0) {
            rt.innerHTML = '<div class="empty">No timestamps found — add times like "[00:15]" to each line to measure response time.</div>';
          } else {
            rt.innerHTML = d.response_times.map(r => `
              <div class="rt-row">
                <span class="rt-delay ${r.slow ? 'slow' : 'ok'}">${r.delay}s</span>
                <span class="rt-text">after: ${esc(r.client_text)}</span>
              </div>`).join('');
          }

          document.getElementById('compScore').textContent =
            (d.compliance_score === undefined || d.compliance_score === null) ? 'n/a' : d.compliance_score;
          const comp = document.getElementById('compliance');
          comp.innerHTML = (d.compliance || []).map(r => {
            const broken = r.status === 'BROKEN';
            return `
              <div class="comp-row">
                <span class="comp-mark ${broken ? 'broken' : 'ok'}">${broken ? 'BROKEN' : 'OK'}</span>
                <div class="comp-body">
                  <div class="rule">${esc(r.rule)}</div>
                  ${broken ? `<div class="ev">heard: "${esc(r.evidence)}"</div>` : ''}
                </div>
              </div>`;
          }).join('');

          const accScore = document.getElementById('accScore');
          accScore.textContent = (d.accuracy_overall === null) ? 'n/a' : d.accuracy_overall;
          const acc = document.getElementById('accuracy');
          if (!d.accuracy || d.accuracy.length === 0) {
            acc.innerHTML = '<div class="empty">No client questions matched the knowledge base, so accuracy could not be checked.</div>';
          } else {
            acc.innerHTML = d.accuracy.map(a => {
              const c = a.accuracy >= 60 ? 'high' : (a.accuracy >= 35 ? 'mid' : 'low');
              const covered = (a.covered || []).map(p => `<div class="kp ok">✓ ${esc(p)}</div>`).join('');
              const missed = (a.missed || []).map(p => `<div class="kp no">✗ ${esc(p)}</div>`).join('');
              return `
                <div class="acc-row">
                  <div class="acc-top">
                    <span class="acc-q">${esc(a.client_question)}<span class="acc-conf">matched: ${esc(a.matched_question)} (${esc(a.confidence)})</span></span>
                    <span class="acc-score ${c}">${a.accuracy}/100</span>
                  </div>
                  <div class="acc-line"><b>Agent said:</b> ${esc(a.agent_answer)}</div>
                  ${covered}${missed}
                  <div class="acc-line"><b>Ideal answer:</b> ${esc(a.ideal_answer)}</div>
                </div>`;
            }).join('');
          }

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
