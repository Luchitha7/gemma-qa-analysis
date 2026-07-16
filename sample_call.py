"""Shared sample call used across the QA analysis parts.

A representative ~5-minute support call (34 turns) between an Agent and a Client.
Deliberately mixed: the agent does some things well (empathy, ownership, clear
next steps) and some things poorly (a defensive moment, a policy dodge), so
there is something real for the QA analysis to catch.
"""

TRANSCRIPT = [
    ("Agent", "Good afternoon, thanks for calling, you're through to Daniel, how can I help today?"),
    ("Client", "Hi Daniel, yeah, I'm calling because I've been charged twice for my subscription this month."),
    ("Agent", "Okay, I'm sorry to hear that, let me take a look at your account and get this sorted for you."),
    ("Client", "Thanks, it's the second time this has happened actually, it happened back in March as well."),
    ("Agent", "I can see the two charges here, both went through on the third, so you're right, that's clearly a duplicate."),
    ("Client", "Right, so it's obviously a problem on your end, not something I did."),
    ("Agent", "I understand why you'd see it that way, though these things can sometimes come from the bank's side too."),
    ("Client", "No, come on, it's the second time, that's not my bank double-charging me for no reason."),
    ("Agent", "That's a fair point, and I apologise, you're right that a repeat like this points to something on our system."),
    ("Client", "Honestly it's really frustrating, I shouldn't have to call up every couple of months to fix this."),
    ("Agent", "You absolutely shouldn't, and I want to make sure this is the last time you have to, not just refund it and move on."),
    ("Client", "Okay, good, because last time they just refunded me and nobody actually looked into why it keeps happening."),
    ("Agent", "That's not good enough, and I'm sorry that was the experience last time, that should have been escalated then."),
    ("Client", "So what are you actually going to do differently this time?"),
    ("Agent", "Two things. First, I'm processing the refund for the duplicate charge right now while we talk."),
    ("Client", "Okay."),
    ("Agent", "Second, I'm raising a billing investigation ticket so an engineer looks at why your account is being double-billed."),
    ("Client", "And will I actually hear back about that, or does it just disappear into a queue somewhere?"),
    ("Agent", "You'll get an email with the ticket number today, and I'm adding a note to have someone update you within five working days."),
    ("Client", "Alright, that's better than last time at least."),
    ("Agent", "I'd also like to add a small credit to your account for the inconvenience of having to chase this again."),
    ("Client", "Oh, okay, I wasn't expecting that, thank you, that's decent of you."),
    ("Agent", "It's the least we can do, you've been a customer for three years and this shouldn't keep happening."),
    ("Client", "Yeah, I've mostly been happy with the service, this billing thing is really the only issue."),
    ("Agent", "That's good to hear, and I've made the refund now, so you'll see that back within three to five business days."),
    ("Client", "Great, and the credit?"),
    ("Agent", "The credit is applied immediately, you'll see it on your next invoice, which will be lower as a result."),
    ("Client", "Perfect, okay, I think that covers everything I called about."),
    ("Agent", "Wonderful, so just to recap, refund processed, credit applied, and a billing investigation raised with an update in five days."),
    ("Client", "Yep, that all sounds right."),
    ("Agent", "Is there anything else at all I can help you with while you're on the line?"),
    ("Client", "No, that's everything, thanks for actually taking it seriously this time."),
    ("Agent", "Of course, and again I'm sorry for the hassle, thanks for your patience and have a great rest of your day."),
    ("Client", "You too, bye."),
]
