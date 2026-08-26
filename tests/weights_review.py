"""Review tool: how do the final scores change if we adjust the weights?

This does NOT need Ollama or any model running. It takes a set of realistic
call profiles (fixed sub-scores for a handful of typical call types) and runs
each one through the current weights and a few alternative weightings, so we can
see at a glance whether the current weights give sensible final scores and where
a change would help or hurt.

The blending logic here is a copy of final_qa_score in qa_agent.py, kept pure so
this script stays lightweight and has no model dependencies.

    python weights_review.py
"""

CURRENT = {
    "agent": 0.45,
    "accuracy": 0.20,
    "compliance": 0.20,
    "conversation": 0.10,
    "response_time": 0.05,
}

ALTERNATIVES = {
    "Compliance first": {
        "agent": 0.40, "accuracy": 0.20, "compliance": 0.30,
        "conversation": 0.05, "response_time": 0.05,
    },
    "Accuracy first": {
        "agent": 0.40, "accuracy": 0.30, "compliance": 0.20,
        "conversation": 0.05, "response_time": 0.05,
    },
    "Balanced": {
        "agent": 0.30, "accuracy": 0.25, "compliance": 0.25,
        "conversation": 0.10, "response_time": 0.10,
    },
}

PROFILES = {
    "Strong all round": {
        "agent": 90, "accuracy": 88, "compliance": 100,
        "conversation": 80, "response_time": 90,
    },
    "Great agent, upset customer": {
        "agent": 88, "accuracy": 85, "compliance": 100,
        "conversation": 40, "response_time": 85,
    },
    "Compliance breach": {
        "agent": 80, "accuracy": 82, "compliance": 40,
        "conversation": 75, "response_time": 80,
    },
    "Wrong info given": {
        "agent": 78, "accuracy": 45, "compliance": 90,
        "conversation": 70, "response_time": 85,
    },
    "Slow to reply": {
        "agent": 82, "accuracy": 80, "compliance": 90,
        "conversation": 72, "response_time": 30,
    },
    "Weak agent handling": {
        "agent": 45, "accuracy": 70, "compliance": 80,
        "conversation": 65, "response_time": 75,
    },
}

def band(score):
    """Same bands the app uses."""
    if score >= 80:
        return "GOOD"
    if score >= 60:
        return "OKAY"
    return "NEEDS IMPROVEMENT"

def blend(parts, weights):
    """Copy of final_qa_score: weighted blend, missing parts dropped."""
    available = {k: v for k, v in parts.items() if v is not None}
    total_weight = sum(weights[k] for k in available)
    if not total_weight:
        return 0.0
    blended = sum(v * weights[k] for k, v in available.items())
    return round(blended / total_weight, 1)

def short_band(b):
    """Compact tag so the table stays narrow."""
    return {"GOOD": "GOOD", "OKAY": "OKAY", "NEEDS IMPROVEMENT": "NEEDS"}[b]

if __name__ == "__main__":
    weight_sets = {"Current": CURRENT, **ALTERNATIVES}
    names = list(weight_sets)

    print("\nFinal score under each weighting (score and band).\n")
    header = f"{'Profile':<28}" + "".join(f"{n:>20}" for n in names)
    print(header)
    print("-" * len(header))

    for pname, parts in PROFILES.items():
        cells = ""
        for n in names:
            score = blend(parts, weight_sets[n])
            cells += f"{f'{score:>5.1f}  {short_band(band(score))}':>20}"
        print(f"{pname:<28}{cells}")

    print("-" * len(header))
    print("\nWhere a band changes from Current, that weighting would move the")
    print("call across a GOOD / OKAY / NEEDS boundary. Those are the cases to")
    print("look at when deciding if the weights need adjusting.\n")

    print("Band changes vs Current:")
    any_change = False
    for pname, parts in PROFILES.items():
        base = band(blend(parts, CURRENT))
        for n, w in ALTERNATIVES.items():
            b = band(blend(parts, w))
            if b != base:
                any_change = True
                print(f"  {pname}: Current={base} -> {n}={b}")
    if not any_change:
        print("  None. Every weighting keeps every profile in the same band.")
    print()
