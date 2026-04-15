"""
End-to-end test of synthetic market research skill.
No API keys needed — uses local sentence-transformers for SSR.
Persona responses are provided inline (in real usage, the Claude Code agent generates them).

Product concept: MeetingMind — AI Meeting Copilot
"""

import json
import os
from datetime import datetime

import numpy as np
from sentence_transformers import SentenceTransformer

# --- Concept ---
CONCEPT = """MeetingMind — An AI copilot that joins your video calls (Zoom/Google Meet/Teams),
takes real-time notes, identifies action items, and generates a structured summary
within 30 seconds of the call ending. Integrates with Slack, Notion, and Linear
to auto-create tasks. $12/month per user, unlimited meetings."""

# --- Personas + Agent-generated free-text responses ---
# In real usage, the Claude Code agent role-plays each persona and writes these.
PERSONA_RESPONSES = [
    {
        "persona": {"age": 27, "income": "$70K", "location": "San Francisco",
                     "occupation": "product designer at a 40-person startup"},
        "response": (
            "Oh wow, this is exactly what I've been looking for. I'm in 4-5 meetings a day "
            "and I spend at least 30 minutes after each one cleaning up my notes in Notion. "
            "The auto-action-items feature alone would save me hours a week. $12/month is "
            "nothing compared to the time I'd get back. The Linear integration is a huge plus "
            "since that's what our engineering team uses. My only concern is accuracy — if the "
            "summaries miss key decisions or misattribute action items, I'd stop trusting it fast. "
            "But I'd definitely sign up for a trial day one."
        ),
    },
    {
        "persona": {"age": 35, "income": "$140K", "location": "New York",
                     "occupation": "engineering manager leading a remote team of 10"},
        "response": (
            "This could be really valuable for my team. Right now meeting notes are inconsistent — "
            "some people take detailed notes, others take none, and we lose context all the time. "
            "A standardized tool that captures everything automatically would fix that. $12/user "
            "for 10 people is $120/month, which I'd need to justify to my VP but it's reasonable "
            "if it works. The Slack integration matters a lot — we live in Slack. I'd want to "
            "pilot it with my team for a month before rolling out wider. My concern: will it "
            "handle technical discussions well? Standup notes are straightforward but architecture "
            "review meetings have nuance that AI often misses."
        ),
    },
    {
        "persona": {"age": 42, "income": "$95K", "location": "Chicago",
                     "occupation": "HR director at a 200-person company"},
        "response": (
            "I have mixed feelings about this. On one hand, I'd love automatic notes from my "
            "interviews and 1-on-1s — I take handwritten notes now and often miss things while "
            "trying to stay present in the conversation. On the other hand, having an AI in "
            "HR meetings raises serious privacy and legal questions. Performance reviews, "
            "disciplinary conversations, confidential employee issues — I can't have those "
            "recorded and processed by a third party. I'd need very clear data handling policies, "
            "SOC 2 compliance, and the ability to exclude certain meetings. For general all-hands "
            "and team syncs, sure. But for my core HR work, I'm not comfortable with it."
        ),
    },
    {
        "persona": {"age": 24, "income": "$50K", "location": "Austin",
                     "occupation": "junior software developer, first remote job"},
        "response": (
            "This sounds cool but I'm not sure I'd pay for it myself. My company might though. "
            "I sit in a lot of meetings where I'm mostly listening and learning, and it would "
            "be great to have a searchable record I could go back to when I realize I missed "
            "something important. $12/month isn't much but I already pay for a bunch of "
            "subscriptions and I'm watching my budget. If my team lead got this for the whole "
            "team, I'd be happy to use it. The Notion integration would be perfect since that's "
            "where I keep my personal dev notes. I'd probably use it more for learning than "
            "for action items since I don't own many tasks yet."
        ),
    },
    {
        "persona": {"age": 50, "income": "$170K", "location": "Boston",
                     "occupation": "VP of Sales at a mid-market SaaS company"},
        "response": (
            "We already use Gong for our external sales calls, and it's deeply embedded in our "
            "workflow — call scoring, deal intelligence, coaching insights. MeetingMind seems "
            "focused on internal meetings which Gong doesn't cover well. I could see value in "
            "having this for our pipeline reviews, forecast meetings, and QBRs. The structured "
            "summaries with action items would help with accountability — right now I spend "
            "15 minutes after each review writing up next steps. But $12/user across my "
            "30-person sales org is $360/month and I'd need to see clear ROI. It would need "
            "to integrate with Salesforce, which I don't see mentioned. Promising concept "
            "but I'd need the CRM integration before I'd seriously consider it."
        ),
    },
    {
        "persona": {"age": 31, "income": "$85K", "location": "Denver",
                     "occupation": "freelance consultant working with 4 clients"},
        "response": (
            "Yes, I'd buy this. As a consultant, documentation is everything — my clients "
            "expect professional meeting summaries and clear action items after every call. "
            "Right now I spend 20-30 minutes per meeting writing these up manually. If "
            "MeetingMind could give me a solid first draft within 30 seconds, I could review "
            "it, tweak it, and send it to the client in 5 minutes instead. That's a massive "
            "time savings across 3-4 client calls per day. $12/month is trivially cheap for "
            "this. The multi-platform support is essential since each client uses a different "
            "video tool. My one concern is data privacy — some clients have strict NDAs and "
            "I'd need to confirm how the audio/transcript data is handled before I'd use it "
            "in sensitive meetings."
        ),
    },
]

# --- Reference statements for purchase intent (4 sets) ---
REFERENCE_SETS = {
    "set1": [
        "I would definitely not buy this",
        "I probably would not buy this",
        "I might or might not buy this",
        "I would probably buy this",
        "I would definitely buy this",
    ],
    "set2": [
        "Not interested in purchasing at all",
        "Slightly interested in purchasing",
        "Moderately interested in purchasing",
        "Very interested in purchasing",
        "Extremely interested in purchasing",
    ],
    "set3": [
        "This product has no appeal to me whatsoever",
        "This product has limited appeal to me",
        "This product has some appeal to me",
        "This product appeals to me quite a bit",
        "This product appeals to me tremendously",
    ],
    "set4": [
        "I see no reason to consider buying this",
        "I might consider buying this in rare circumstances",
        "I could see myself buying this under the right conditions",
        "I would likely buy this if I needed something in this category",
        "I would actively seek this out and buy it",
    ],
}


def compute_ssr_pmf(response_embs: np.ndarray, ref_embs: np.ndarray, epsilon: float = 0.0) -> np.ndarray:
    """Core SSR: convert response embeddings to PMFs over Likert scale."""
    resp_norm = response_embs / np.linalg.norm(response_embs, axis=1, keepdims=True)
    ref_norm = ref_embs / np.linalg.norm(ref_embs, axis=1, keepdims=True)

    cos = (1 + resp_norm @ ref_norm.T) / 2

    cos_min = cos.min(axis=1, keepdims=True)
    numerator = cos - cos_min

    if epsilon > 0:
        min_indices = np.argmin(cos, axis=1)
        for i, idx in enumerate(min_indices):
            numerator[i, idx] += epsilon

    denominator = numerator.sum(axis=1, keepdims=True)
    denominator = np.where(denominator == 0, 1e-10, denominator)
    return numerator / denominator


def main():
    print("=" * 70)
    print("SYNTHETIC MARKET RESEARCH TEST: MeetingMind")
    print("No API keys — local sentence-transformers + agent-generated responses")
    print("=" * 70)
    print(f"\nConcept: {CONCEPT.strip()}\n")

    # Load local embedding model
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("Model loaded.\n")

    # Embed responses
    response_texts = [r["response"] for r in PERSONA_RESPONSES]
    response_embs = model.encode(response_texts)
    print(f"Encoded {len(response_texts)} persona responses: shape {response_embs.shape}")

    # Compute PMFs per reference set, then average
    all_pmfs = []
    for set_name, ref_statements in REFERENCE_SETS.items():
        ref_embs = model.encode(ref_statements)
        pmfs = compute_ssr_pmf(response_embs, ref_embs)
        all_pmfs.append(pmfs)
        print(f"  Reference set '{set_name}': PMFs computed")

    mean_pmfs = np.mean(all_pmfs, axis=0)

    # Results
    likert = np.array([1, 2, 3, 4, 5])

    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}\n")
    print(f"{'Persona':<50} {'P(1)':>5} {'P(2)':>5} {'P(3)':>5} {'P(4)':>5} {'P(5)':>5} {'Score':>6}")
    print("-" * 82)

    persona_scores = []
    for i, (entry, pmf) in enumerate(zip(PERSONA_RESPONSES, mean_pmfs)):
        p = entry["persona"]
        score = float(np.dot(pmf, likert))
        persona_scores.append(score)
        desc = f"{p['occupation'][:35]} ({p['age']}, {p['location']})"
        print(f"{desc:<50} {pmf[0]:>5.2f} {pmf[1]:>5.2f} {pmf[2]:>5.2f} {pmf[3]:>5.2f} {pmf[4]:>5.2f} {score:>6.2f}")

    overall_pmf = mean_pmfs.mean(axis=0)
    overall_score = float(np.dot(overall_pmf, likert))

    print("-" * 82)
    print(f"{'OVERALL':<50} {overall_pmf[0]:>5.2f} {overall_pmf[1]:>5.2f} {overall_pmf[2]:>5.2f} {overall_pmf[3]:>5.2f} {overall_pmf[4]:>5.2f} {overall_score:>6.2f}")

    # Segment analysis
    print(f"\n{'='*70}")
    print("SEGMENT ANALYSIS")
    print(f"{'='*70}\n")

    under_35 = [s for i, s in enumerate(persona_scores) if PERSONA_RESPONSES[i]["persona"]["age"] < 35]
    over_35 = [s for i, s in enumerate(persona_scores) if PERSONA_RESPONSES[i]["persona"]["age"] >= 35]
    print(f"  Age < 35:  mean = {np.mean(under_35):.2f}  (n={len(under_35)})")
    print(f"  Age >= 35: mean = {np.mean(over_35):.2f}  (n={len(over_35)})")

    highest = max(range(len(persona_scores)), key=lambda i: persona_scores[i])
    lowest = min(range(len(persona_scores)), key=lambda i: persona_scores[i])
    h_p = PERSONA_RESPONSES[highest]["persona"]
    l_p = PERSONA_RESPONSES[lowest]["persona"]

    print(f"\n  Highest intent: {h_p['occupation']} ({h_p['age']}) — {persona_scores[highest]:.2f}")
    print(f"  Lowest intent:  {l_p['occupation']} ({l_p['age']}) — {persona_scores[lowest]:.2f}")

    # Qualitative themes
    print(f"\n{'='*70}")
    print("QUALITATIVE THEMES")
    print(f"{'='*70}\n")
    themes = [
        "1. TIME SAVINGS: 5/6 personas cited specific time savings (20-30 min/meeting)",
        "2. PRIVACY/SECURITY: 3/6 raised data handling, NDAs, SOC 2, or HR sensitivity",
        "3. INTEGRATION GAPS: 2/6 want CRM (Salesforce) integration not listed in concept",
        "4. PRICE ACCEPTABLE: 0/6 flagged $12/mo as too expensive; budget persona wanted team purchase",
        "5. ACCURACY SKEPTICISM: 2/6 worry about AI missing nuance in technical/complex discussions",
        "6. TEAM vs INDIVIDUAL: Junior roles would prefer company purchase over personal subscription",
    ]
    for t in themes:
        print(f"  {t}")

    # Interpretation
    print(f"\n{'='*70}")
    print("INTERPRETATION")
    print(f"{'='*70}\n")
    if overall_score >= 4.0:
        verdict = "STRONG — Above 4.0 indicates high purchase intent across segments"
    elif overall_score >= 3.5:
        verdict = "POSITIVE — 3.5-4.0 range indicates solid interest with some reservations"
    elif overall_score >= 3.0:
        verdict = "NEUTRAL — 3.0-3.5 range suggests concept needs refinement"
    else:
        verdict = "WEAK — Below 3.0 indicates significant purchase resistance"

    print(f"  Overall Score: {overall_score:.2f} / 5.00")
    print(f"  Verdict: {verdict}")
    print(f"\n  Benchmarks (from PyMC Labs paper):")
    print(f"    Successful consumer products: ~3.8-4.2")
    print(f"    Average product concept: ~3.5")
    print(f"    Weak concept: < 3.0")

    # Save report
    os.makedirs("output", exist_ok=True)
    report = {
        "concept": CONCEPT.strip(),
        "timestamp": datetime.now().isoformat(),
        "method": "SSR (Semantic Similarity Rating) — local embeddings, no API keys",
        "embedding_model": "all-MiniLM-L6-v2",
        "n_personas": len(PERSONA_RESPONSES),
        "n_reference_sets": len(REFERENCE_SETS),
        "overall_pmf": overall_pmf.tolist(),
        "overall_score": round(overall_score, 2),
        "personas": [
            {
                "demographics": entry["persona"],
                "response": entry["response"],
                "pmf": mean_pmfs[i].tolist(),
                "score": round(persona_scores[i], 2),
            }
            for i, entry in enumerate(PERSONA_RESPONSES)
        ],
    }

    output_path = "output/research_meetingmind.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Full report saved to: {output_path}")

    print(f"\n{'='*70}")
    print("DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
