---
summary: Controls for Janus, the engine behind Linda: her model, limits, standing instructions and what she has learned.
---

## What it's for
This page controls Janus, the engine Linda runs on: whether she answers at all, which AI model she uses, how many steps and how long she may take on one message, any standing instructions she should always follow, and whether she keeps notes and skills between conversations. It also shows whether Janus is current with its latest build and lets you test the connection.

## Set it up
Switch Linda on, and decide where her model comes from: the store's own AI provider, set in Settings → AI, or a provider and model you pin here just for her, with its own key. Add standing instructions if you want her to always answer a certain way — a language, a house style, anything consistent. Run the connection test once to confirm she answers.

## Common tasks
- Turn Linda on or off for everyone in [](page:engine).
- Pin a specific provider and model for Linda, instead of the store's default.
- Add standing instructions Linda should always follow.
- Set how many tool steps and how many seconds she gets for one message.
- Pick backup providers to use if the main one fails partway through an answer.
- Run the connection test to confirm Linda can reach her model.
- Delete a note, a skill, or all of Linda's lessons you don't want her using any more.
- Check whether a newer Janus build is available on GitHub and whether it passed its checks.

## Good to know
Your own reply in the chat is the only thing that approves a change — nothing on this page grants Linda extra permission to act without asking first. She has no shell, file or code access and cannot open web pages; she can only search the web for outside facts, and only while that is switched on. Keeping Janus current from GitHub is optional and only ever switches to a build that has passed its checks; turning it off just keeps the one the server was already built with.
