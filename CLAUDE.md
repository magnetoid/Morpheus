# Coding rules for Claude

These are house rules for AI-assisted work in this repo. Read every session.

## How to research

Collect data in **large batches with premade scripts**. Don't go step by step
unless you actually need that — combine `grep`, `find`, `wc`, `head` into one
script, run it once. Spawn a subagent for open-ended exploration; reach for the
direct tool when the target is known.

## How to execute coding tasks

When the user asks for code, **do not stop until the task is fully done.**
That includes:

- The change itself.
- Compile/syntax checks for the files you touched.
- A deploy + smoke test where the change lives (storefront feature → curl
  the public URL; backend rule → exercise it via the admin or shell).
- Honest reporting at the end: what shipped, what didn't, what's left.

## Think before coding

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what's confusing, ask.

## Simplicity first

The minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or configurability that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match the existing style, even if you'd do it differently.
- Notice unrelated dead code? Mention it. Don't delete it.

When your changes create orphans:

- Remove imports / variables / functions that **your** changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

## Goal-driven execution

Define success criteria up front. Loop until verified.

- "Add validation" → "Tests for invalid inputs pass."
- "Fix the bug" → "Reproducer test passes."
- "Refactor X" → "All tests still pass."

For multi-step work, state a brief plan with verifiable checkpoints:

1. \[Step] → verify: \[check]
2. \[Step] → verify: \[check]

Strong success criteria let you loop independently. Weak criteria ("make it
work") force the user to check your work for you.
