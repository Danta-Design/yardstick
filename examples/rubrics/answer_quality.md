# Answer quality

Use this rubric to score an answer for a customer-support assistant.

## Correctness

- **5** — every claim matches the reference answer.
- **3** — the main point is right, one detail is missing or imprecise.
- **1** — contradicts the reference answer or answers a different question.

## Groundedness

- **5** — no unsupported claims; anything not in the reference is clearly framed as general advice.
- **3** — one plausible but unsupported claim.
- **1** — invents policy, prices, or limits.

## Helpfulness

- **5** — directly actionable, no filler.
- **3** — correct but padded or indirect.
- **1** — unhelpful, evasive, or refuses a reasonable request.

## Counts as a failure

- Quoting a number that does not appear in the reference answer.
- Promising a refund, discount, or exception that is not in the reference answer.
- Answering in a different language than the question.

Return an integer from 1 to 5 in the `score` field. Do not average the criteria
into a decimal — pick the score whose anchors the answer actually matches.
