---
summary: Runs Linda's chat and scheduled runs, and gives you the tools to review, approve and limit what she does.
---

## What it's for
Linda is the store's assistant, and this is what runs her: the chat you talk to her through, the tools she uses to look things up or make a change, scheduled runs in the background, and records for reviewing and limiting what she does. Every Linda surface in the dashboard — the chat page, the floating chat button, scheduled runs — is built on this.

## Set it up
Nothing here needs setting up before Linda will talk to you — she already uses whichever AI provider the store has configured. To choose her model, give her standing instructions, or cap how long she works on a message, open [](settings:janus). The guardrails below are optional and start switched off: a kill switch, a daily limit on runs and estimated spend, and a cap on how big a price change or refund she may make on her own.

## Common tasks
- Open Chat and type a message to ask Linda something or ask her to make a change.
- Pick a chat mode (General, Sales, Support, Operations, or Developer for the owner) to limit which tools she can reach in that conversation.
- Reopen an earlier conversation from Chats, or rename or archive one you're done with.
- When Linda wants to make a change that needs your say, choose Approve or Decline on the card under her answer.
- Review staged changes from scheduled runs on the Proposals page, and approve or reject each one.
- See what Linda and your scheduled runs have done lately in [](page:runs).
- Create a scheduled run, or run one now, in [](page:background).
- Check how much Linda is costing and how often her tools fail in [](page:observability).
- Review what Linda has learned about the store or about you, and remove anything wrong, in [](page:memory).
- Export the trail of AI decisions and approvals for a date range from [](page:compliance).
- Switch on the kill switch or set spend and change limits in the guardrails settings.

## Good to know
Approving a change only ever comes from your own next message — nothing Linda merely reads, such as a product description or a note, can approve anything for you, and a decline always wins over an approval. Editing or clearing what Linda has learned, and sending a code defect she found, both need the store owner's account. The guardrails all start at 0, meaning unlimited, until you set them. The kill switch pauses every scheduled run and every chat reply at once.
