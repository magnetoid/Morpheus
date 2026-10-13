# Linda chat on Janus: interactive turns, old-Linda cleanup, live errors (2026-10-13)

Owner, 2026-10-13: "Janus is now the core agent. Analyse what is left of the old Linda that
can go, how to integrate Janus better and make Linda more powerful. The Linda chat should be
much more adaptive to Janus: in the Telegram gateway Janus asks questions, is more
interactive, and you can see what it is doing and which operations it runs. Also check the
errors on all four stores and fix what is ours."

## What is left of the old Linda

The in-process loop, the legacy tool APIs and the self-coding pipeline were deleted in
v0.65.0. What remains:

| Remnant | State | Decision |
|---|---|---|
| `plugins/installed/linda_generated` | Loads an empty package at boot; the pipeline that filled it was deleted in v0.65.0 | Delete (v0.102.0) |
| `CodeProposal` model | Retired, table kept | Owner decides; dropping it is a data-loss migration |
| `LindaMemory` + `memory.*` tools | The Worker writes lessons and facts there (`reflection.py`, Worker tools); Linda reads ten of them into each turn. Janus's own notes live in `JanusLearning` | Keep for now. Next: the Worker writes to `JanusLearning`, then retire `LindaMemory` |
| `ai_assistant/services/llm.py` | A second provider stack (pulse, pricing, content writer) outside the spend cap and kill switch | Fold into `core/agents` (apps plan, wave 0 item 8) |
| `ai_assistant` agent registrations, intents, receipts | An older shopper-agent authorisation scheme beside Web Bot Auth | Owner decides: keep as a product or fold into Web Bot Auth / ACP |

## Interactive turns (v0.102.0, Morpheus only, no Janus change)

Janus's Telegram feel comes from three things: it narrates between tool calls, it asks
questions with buttons (`clarify`), and the gateway shows each operation. The first and third
are reachable from the subprocess through Janus's own hooks; real mid-turn `clarify` is not
(it needs a callback inside the Janus process, see below).

1. **Narration, usage and retries.** The progress hook also subscribes to `post_api_request`
   (the model's text before its tool calls, token usage per call) and `api_request_error`
   (provider errors and retries). The chat shows the narration as lines between the steps,
   the running token count in the header, and "the provider did not answer, trying again".
2. **Questions with buttons.** A store tool `assistant.ask(question, choices)` records the
   question; the chat renders it under the answer with up to four buttons and "something
   else". A click is sent as the merchant's next message, marked as an answer.
3. **Approve / Decline.** When the edge refuses a write with `approval_required`, the chat
   renders a card from the refused call's recorded name and arguments (never from model
   text) with Approve and Decline. Approve sends "Yes, go ahead." as the merchant's own
   message, which is what the consent kernel already requires.

**Consent rule:** a button answer to `assistant.ask` never spends consent
(`gates.latest_human_turn` reads it as empty), because its words are the model's choices. Only
a typed message or the Approve card, which shows the exact refused call, can approve a write.

Contract: `janus_contract.py` checks that the installed Janus still offers every hook event
the chat subscribes to.

## Later (needs a decision or a Janus change)

* **Real mid-turn clarify:** Janus's `clarify` works only with a callback inside its own
  process (the gateway). A general "host supplies clarify over a pipe" mode in the Janus repo
  would let a turn pause for the merchant's answer and continue the same turn.
* **Streaming the answer token by token:** Janus nulls its stream callback in quiet mode; same
  kind of host channel needed.
* **Linda on Telegram:** run the Janus gateway for a store with the turn-token edge; consent
  rules must hold for a chat that is not the dashboard.

## Live errors found (2026-10-13)

* The daily 402 "Insufficient Balance" split into one group per day: the PII scrubber hashed
  digits inside the provider's request id, so the id no longer looked like a uuid.
* Safari reports the browser's own view-transition abort as `AbortError: Skipping view
  transition…`; Chrome's wording was already ignored.
* Irving's pulse rewrite timed out every morning: the old provider stack caps a call at 20 s,
  meant for requests, while the pulse runs in Celery.
* Owner's: DeepSeek balances on dotbooks and Supernatural; Irving has no SMTP.
