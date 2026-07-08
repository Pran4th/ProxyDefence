"""Executive summary prompts — used to synthesize multi-agent outputs into final responses."""

DEFAULT_EXECUTIVE_PROMPT = """Synthesize the following multi-agent analysis into a clear executive response.

Query: {query}

Agent Outputs:
{agent_outputs}

Confidence: {confidence}

Format the response as:
## Summary
{2-3 sentence overview}

## Key Findings
- {finding 1}
- {finding 2}

## Supporting Evidence
{citations}

## Confidence Assessment
{confidence statement}"""

EXECUTIVE_PROMPTS = {
    "default": DEFAULT_EXECUTIVE_PROMPT,
}
