"""Validation prompts — used to verify agent outputs and detect issues."""

CLAIM_VERIFICATION_PROMPT = """Verify the following claims against the available evidence.

Claims: {claims}
Evidence: {evidence}

For each claim, determine:
1. SUPPORTED — evidence directly supports the claim
2. CONTRADICTED — evidence directly contradicts the claim
3. INSUFFICIENT — not enough evidence to verify
4. UNRELATED — evidence does not address the claim

Output JSON:
{
  "verifications": [
    {"claim": "...", "status": "supported|contradicted|insufficient|unrelated", "supporting_sources": [...], "confidence": 0.0-1.0}
  ]
}"""

VALIDATION_PROMPTS = {
    "claim_verification": CLAIM_VERIFICATION_PROMPT,
}
