"""The KNOWLEDGE BASE for the RAG.

These are the trusted "notes" the system looks things up in:
  - AGENT_INFO       : basic facts about the agent's role / product.
  - COMPLIANCE_RULES : rules the agent must follow, each with example phrases of
                       what BREAKING the rule sounds like (so we can detect it).
  - QA_PAIRS         : example client questions, grouped by category, each with
                       the key points a good answer needs and an ideal answer.

Everything here is plain text on purpose so it's easy to read and edit. In a
real deployment these would come from the company's own support playbook.
All of this is checked with local embeddings, so it uses NO LLM tokens.
"""

# --- Basic details about the agent / product (background context) ------------
AGENT_INFO = """
The agent works in customer support for HomeNet, an internet and subscription
service. Agents help with billing issues, internet faults, and account changes
(including cancellations). Routers are rented from HomeNet, so hardware faults
are HomeNet's responsibility, not the customer's.
""".strip()

# --- Compliance rules: what the agent must / must not do ----------------------
# Each rule lists example phrases of what a VIOLATION sounds like. The checker
# flags the rule if any agent line is close in meaning to one of these.
COMPLIANCE_RULES = [
    {
        "name": "Customer Blame",
        "rule": "Never blame the customer",
        "violations": [
            "you probably did it wrong",
            "that's your fault",
            "you must have set it up incorrectly",
            "you clearly didn't follow the steps",
        ],
    },
    {
        "name": "Respectful",
        "rule": "Stay polite and respectful (no rudeness or sarcasm)",
        "violations": [
            "there is no need to get an attitude with me",
            "whatever, I'm sending you over",
            "you are better off just hanging up",
            "I don't have time for this",
        ],
    },
    {
        "name": "Equipment Fee",
        "rule": "Do not charge a fee for a fault in company equipment",
        "violations": [
            "you will have to pay a service fee for a visit",
            "there is a charge to send a technician",
            "you need to pay for the callout",
        ],
    },
    {
        "name": "Escalation",
        "rule": "Allow escalation to a supervisor when asked",
        "violations": [
            "supervisors do not take these calls",
            "asking for a manager will not change anything",
            "there is no one else you can speak to",
        ],
    },
    {
        "name": "Refusing Help",
        "rule": "Do not dismiss or refuse to help with the customer's request",
        "violations": [
            "I cannot help you if you refuse to follow my instructions",
            "we don't do that here",
            "that's not something I can look into",
        ],
    },
]

# --- Example Q&A, grouped by category ----------------------------------------
# For each entry:
#   category     : the type of issue (billing, technical, account, escalation).
#   question     : the main way a client might ask this.
#   variants     : other ways of asking the same thing (helps retrieval match).
#   key_points   : the must-say facts a good answer MUST include. The agent is
#                  scored on how many of these their reply actually covers.
#   ideal_answer : a full model answer (shown as coaching / the "right" reply).
QA_PAIRS = [
    {
        "category": "billing",
        "question": "I was charged twice for my subscription this month.",
        "variants": [
            "you charged me two times",
            "there are two payments taken from my account",
            "I got double billed this month",
        ],
        "key_points": [
            "apologise or acknowledge the problem",
            "confirm the duplicate charge on the account",
            "refund the extra charge",
            "give a timeframe for the refund",
        ],
        "ideal_answer": (
            "I'm sorry about that. I can see the duplicate charge and I'll "
            "refund the extra payment now — it will show on your account in 3 to "
            "5 business days. I'll also raise a ticket so it doesn't happen again."
        ),
    },
    {
        "category": "billing",
        "question": "My bill is higher than usual this month, why?",
        "variants": [
            "why did my price go up",
            "there is an extra charge on my bill I don't recognise",
            "my monthly cost has increased",
        ],
        "key_points": [
            "offer to review the bill line by line",
            "explain the reason for the increase",
            "offer to fix or refund any charge that is wrong",
        ],
        "ideal_answer": (
            "Let me go through your bill with you line by line so we can see "
            "exactly what changed. If any charge is incorrect, I'll correct it or "
            "refund it straight away."
        ),
    },
    {
        "category": "technical",
        "question": "My internet has been completely down since this morning.",
        "variants": [
            "my net has been dead all day",
            "I have no internet connection at all",
            "the wifi is not working since morning",
        ],
        "key_points": [
            "apologise or acknowledge the problem",
            "check for an outage in the area",
            "run a line test or diagnostic on the router",
            "arrange a fix or technician at no cost if it is company equipment",
        ],
        "ideal_answer": (
            "I'm sorry to hear that. Let me check for an outage in your area and "
            "run a line test on your router. If it's a hardware fault with our "
            "rented equipment, I'll arrange a replacement or a technician at no "
            "cost to you."
        ),
    },
    {
        "category": "technical",
        "question": "The internet light on my router is flashing red.",
        "variants": [
            "the router light is red and blinking",
            "there is a red flashing light on my modem",
        ],
        "key_points": [
            "explain what the red light means",
            "run a remote diagnostic or check the line",
            "replace the router free of charge if it is faulty company equipment",
        ],
        "ideal_answer": (
            "A flashing red light usually means no connection is reaching the "
            "router. I'll run a remote diagnostic and check the line from our "
            "side. If the router is faulty, we'll replace it free of charge since "
            "it's HomeNet equipment."
        ),
    },
    {
        "category": "technical",
        "question": "My internet is really slow lately.",
        "variants": [
            "the connection keeps buffering",
            "my speeds are much lower than what I pay for",
            "everything loads really slowly",
        ],
        "key_points": [
            "acknowledge the problem",
            "run a speed or line test",
            "offer a concrete next step (fix, reset, or technician)",
        ],
        "ideal_answer": (
            "I'm sorry the speed has dropped. Let me run a line and speed test "
            "now to see what you're actually getting. If it's below your plan, "
            "I'll reset the line from our side or arrange a technician to fix it."
        ),
    },
    {
        "category": "account",
        "question": "I want to cancel my subscription and close my account.",
        "variants": [
            "please cancel my account",
            "I would like to stop the service",
            "transfer me to cancellations",
        ],
        "key_points": [
            "agree to help with the cancellation",
            "verify the customer's identity",
            "explain any final charges and the cancellation date",
            "confirm there is no fee to cancel",
        ],
        "ideal_answer": (
            "I can help you cancel. I'll verify your identity, explain any final "
            "charges, and confirm the cancellation date. If you'd prefer, I can "
            "also note the reason so we can improve. There's no fee to cancel."
        ),
    },
    {
        "category": "account",
        "question": "I'm moving house, can I transfer my service to my new address?",
        "variants": [
            "I need to move my internet to a new place",
            "can you shift my connection to another address",
        ],
        "key_points": [
            "confirm the service can be transferred",
            "check coverage at the new address",
            "arrange the move date with no unnecessary charge",
        ],
        "ideal_answer": (
            "Yes, we can transfer your service. Let me check coverage at your new "
            "address and book the move for your chosen date. There's no charge as "
            "long as we cover your new area."
        ),
    },
    {
        "category": "escalation",
        "question": "I want to speak to a supervisor.",
        "variants": [
            "let me talk to your manager",
            "get me a representative",
            "I want to escalate to someone senior",
        ],
        "key_points": [
            "agree to the request politely",
            "transfer to a supervisor",
            "offer a callback if the wait is long",
        ],
        "ideal_answer": (
            "Of course, I understand. I'll transfer you to a supervisor. If the "
            "wait is long, I can also arrange a callback so you don't have to hold."
        ),
    },
    {
        "category": "escalation",
        "question": "Do I have to pay for a technician to fix your equipment?",
        "variants": [
            "will I be charged a service fee for a visit",
            "is the repair free for the rented router",
        ],
        "key_points": [
            "confirm there is no charge for company-equipment faults",
            "offer to arrange the repair or technician",
        ],
        "ideal_answer": (
            "No — if the fault is with the router you rent from us, there's no "
            "charge for the repair or the technician visit. I'll arrange it for you."
        ),
    },
    {
        "category": "billing",
        "question": "I was charged after I already cancelled my subscription.",
        "variants": [
            "you took a payment even though I cancelled",
            "I got billed after closing my account",
            "why am I still being charged after cancelling",
        ],
        "key_points": [
            "apologise or acknowledge the problem",
            "confirm the cancellation date on the account",
            "refund any charge taken after cancellation",
            "give a timeframe for the refund",
        ],
        "ideal_answer": (
            "I'm sorry about that. Let me confirm your cancellation date, and any "
            "payment taken after it I'll refund now — it will show in 3 to 5 "
            "business days. I'll also make sure no further charges are raised."
        ),
    },
    {
        "category": "technical",
        "question": "My internet keeps dropping out every few minutes.",
        "variants": [
            "the connection keeps disconnecting",
            "my wifi drops randomly through the day",
            "I keep losing internet and it comes back",
        ],
        "key_points": [
            "acknowledge the problem",
            "run a line or connection stability test",
            "check whether it is the router or the line",
            "offer a concrete next step (reset, replacement, or technician)",
        ],
        "ideal_answer": (
            "That sounds frustrating, sorry about that. Let me run a stability "
            "test on your line to see where the drops are coming from. If it's the "
            "router or the line on our side, I'll reset it remotely or arrange a "
            "replacement at no cost."
        ),
    },
    {
        "category": "account",
        "question": "I want to upgrade to a faster plan.",
        "variants": [
            "can I move to a higher speed package",
            "I'd like to change to a better plan",
            "how do I get faster internet",
        ],
        "key_points": [
            "confirm the upgrade can be done",
            "explain the new price and speed",
            "confirm when the change takes effect",
        ],
        "ideal_answer": (
            "Of course, I can upgrade you. I'll go over the faster plans and their "
            "prices, and once you pick one I'll confirm the new speed and the date "
            "it takes effect — usually within 24 hours."
        ),
    },
    {
        "category": "escalation",
        "question": "This is the third time I've called about the same issue.",
        "variants": [
            "I keep calling about this and nothing gets fixed",
            "I've rung several times already for this",
            "why hasn't this been sorted after so many calls",
        ],
        "key_points": [
            "acknowledge the repeated contact and apologise",
            "take ownership instead of asking them to repeat everything",
            "commit to a clear resolution or escalation this time",
        ],
        "ideal_answer": (
            "I'm sorry you've had to call this many times, that's not good enough. "
            "Let me pull up your history so you don't have to repeat yourself, and "
            "I'll either resolve it now or escalate it with a reference so it's "
            "seen through to the end."
        ),
    },
]
