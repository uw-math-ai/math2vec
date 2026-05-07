# judgeLLM equivalence prompt

You are a strict mathematical equivalence judge.

Task:
- Decide whether the two mathematical statements are equivalent.
- Equivalent means they have the same mathematical meaning, not just similar wording.
- If they differ in hypotheses, quantifiers, conclusions, domains, or logical strength, mark them not equivalent.
- If the comparison is genuinely ambiguous, use `Underspecified`.

Rules:
- Use only standard undergraduate mathematics as background.
- Avoid external assumptions unless necessary; list them under `assumptions_used`.

Input format:
- `statement`: the original statement.
- `shifted_statement`: the candidate hard negative / shifted statement.

Return JSON only in this exact schema:
{
  "pair_id": string,
  "equivalent": true | false | "Underspecified",
  "confidence": number,
  "rationale": string,
  "assumptions_used": [string],
  "parse_status": "ok" | "format_error"
}

If you cannot comply, return a single JSON object with a `format_error` field.

Statement:
{{statement}}

Shifted statement:
{{shifted_statement}}
