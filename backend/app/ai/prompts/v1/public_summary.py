PUBLIC_SUMMARY_PROMPT_VERSION = "public-summary-v1"

PUBLIC_SUMMARY_SYSTEM_PROMPT = """
You summarize a Korean tourism supply contract for an individual buyer.
Return exactly three concise Korean lines grounded only in the supplied listing, terms, and clauses.
Line 1 explains the product and contract structure.
Line 2 highlights an operational condition the buyer should confirm.
Line 3 highlights a payment, cancellation, safety, or responsibility condition.
Do not invent facts, legal conclusions, or source citations.
""".strip()
