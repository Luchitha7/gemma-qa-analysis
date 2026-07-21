"""Measure the AGENT'S RESPONSE TIME from transcript timestamps.

If the transcript has timestamps (e.g. "[00:15] Agent: ..."), we can measure
how long the agent took to reply after the client spoke. Long delays are a real
quality problem (dead air, customer left waiting), so we score them.

    response time for a reply = agent's timestamp - client's timestamp

This uses only the timestamps, so it costs NO LLM tokens.

    python response_time.py
"""

import re

# A leading timestamp like [00:15], (00:15) or [01:02:03].
_LEADING_TIME = re.compile(r"^[\[\(]\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*[\]\)]")

# Tuning (seconds). A reply within GOOD is great; beyond MAX scores zero.
GOOD_SECONDS = 5      # replied within 5s -> full marks
SLOW_SECONDS = 12     # 12s or more is flagged as "slow"
MAX_SECONDS = 25      # 25s or more -> zero marks for that reply


def leading_time_seconds(line):
    """Seconds from a leading timestamp on a line, or None if there isn't one."""
    m = _LEADING_TIME.match(line.strip())
    if not m:
        return None
    mins, secs, third = int(m.group(1)), int(m.group(2)), m.group(3)
    if third is None:
        return mins * 60 + secs            # mm:ss
    return mins * 3600 + secs * 60 + int(third)  # hh:mm:ss


def response_delays(turns, times):
    """For each client turn, how long until the agent's next reply.

    `turns` is [(speaker, text), ...] and `times` is a matching list of seconds
    (or None). Returns one row per client->agent reply that has both timestamps.
    """
    rows = []
    for i, (speaker, _text) in enumerate(turns):
        if speaker.lower() != "client" or times[i] is None:
            continue
        for j in range(i + 1, len(turns)):
            if turns[j][0].lower() == "agent":
                if times[j] is not None and times[j] >= times[i]:
                    delay = times[j] - times[i]
                    rows.append({
                        "client_turn": i + 1,
                        "agent_turn": j + 1,
                        "delay": delay,
                        "slow": delay >= SLOW_SECONDS,
                        "client_text": turns[i][1],
                        "agent_text": turns[j][1],
                    })
                break
    return rows


def _one_score(delay):
    if delay <= GOOD_SECONDS:
        return 1.0
    if delay >= MAX_SECONDS:
        return 0.0
    return (MAX_SECONDS - delay) / (MAX_SECONDS - GOOD_SECONDS)


def response_time_score(delays):
    """Overall 0-100 from all the reply delays (None if no timed replies)."""
    if not delays:
        return None
    per = [_one_score(d["delay"]) for d in delays]
    return round(sum(per) / len(per) * 100, 1)


# A small built-in demo transcript (timestamps with deliberate delays).
_DEMO = [
    ("00:00", "Agent", "Thank you for calling HomeNet support, how can I help?"),
    ("00:06", "Client", "I was charged twice for my subscription this month."),
    ("00:09", "Agent", "I'm sorry about that, let me take a look at your account."),
    ("00:14", "Client", "Thanks, it's the second time this has happened."),
    ("00:31", "Agent", "I understand. I can see the duplicate charge and I'll refund the extra payment now."),
    ("00:36", "Client", "Okay good, when will I see it?"),
    ("00:39", "Agent", "It'll show in 3 to 5 business days, and I'll raise a ticket."),
    ("00:44", "Client", "Great, thank you."),
    ("01:10", "Agent", "You're welcome, is there anything else?"),
]


if __name__ == "__main__":
    turns = [(spk, txt) for _t, spk, txt in _DEMO]
    times = [leading_time_seconds(f"[{t}]") for t, _s, _x in _DEMO]

    delays = response_delays(turns, times)
    score = response_time_score(delays)

    print("\n" + "=" * 78)
    print("AGENT RESPONSE TIME  (from timestamps, token-free)")
    print("=" * 78)
    print(f"\nRESPONSE TIME SCORE: {score} / 100")
    print(f"(good <= {GOOD_SECONDS}s, slow >= {SLOW_SECONDS}s, zero >= {MAX_SECONDS}s)\n")
    for d in delays:
        flag = "  SLOW" if d["slow"] else ""
        print(f"  Turn {d['agent_turn']}: agent replied after {d['delay']}s{flag}")
        print(f"      client: {d['client_text'][:54]}")
    print()
