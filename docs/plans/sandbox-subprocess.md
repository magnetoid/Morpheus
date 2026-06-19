# Sandbox subprocess isolation (Phase 4)

## Context

`core/agents/sandbox.py` runs agent-authored Python (the `run_python` tool /
Linda composing tools in code) behind layered defenses: AST validation
(forbids `import`, `async`, `yield`, `global`/`nonlocal`, dunder access, and
names like `__import__`/`open`/`eval`/`exec`/`getattr`), a curated `builtins`
allow-list, and a **daemon-thread** runner with a `Thread.join(timeout)`.

The known weakness (flagged in the file and in CLAUDE.md): **a Python thread
can't be force-killed.** An infinite loop or a `while True: pass` outlives the
timeout — the runner returns an error but the thread keeps burning a core
until process exit. A leaked-thread counter refuses new runs after 5 leaks
(DoS backstop), which means a few malicious/buggy scripts can wedge the whole
sandbox until the worker restarts. Acceptable for trusted first-party code;
unsuitable for anything less.

## Goal

Replace the thread runner with a **hard-killable subprocess** so timeouts and
runaway loops are terminated for real (`SIGKILL`), removing the leaked-thread
backstop entirely. Keep the AST validation + curated builtins exactly as-is —
defense in depth.

## Approach

A child-process executor in `core/agents/sandbox.py` (or a sibling
`sandbox_runner.py` used as `python -m`):

1. **Parent** (`run_sandboxed`):
   - Run the existing AST validation in-parent first (fail fast, no spawn for
     obviously-bad code).
   - `subprocess.Popen([sys.executable, '-m', 'core.agents.sandbox_runner'],
     stdin=PIPE, stdout=PIPE, stderr=PIPE, start_new_session=True)` — new
     session so we can kill the whole process group.
   - Send `{source, args}` as JSON on stdin.
   - `proc.communicate(timeout=…)`; on `TimeoutExpired`, `os.killpg(pgid,
     SIGKILL)` then reap. No survivable runaway.
   - Parse `{ok, result|error}` from stdout. Treat non-JSON / non-zero exit as
     a sandbox error.
2. **Child** (`sandbox_runner.__main__`):
   - Re-run AST validation (never trust the parent did it).
   - Apply resource limits where available (`resource.setrlimit` for CPU
     seconds + address space on POSIX; best-effort, skipped on platforms
     without it).
   - `exec(compiled, {'__builtins__': CURATED}, locals)` — same curated
     builtins as today.
   - Emit `{ok, result}` (JSON, `default=str`) on stdout; `{ok: False, error}`
     on any exception.

### The `call` bridge
Today sandboxed code can call back into agent tools in-process. Across a
process boundary that needs IPC:
- **Option A (recommended first cut):** disallow tool callbacks inside
  `run_python` — the sandbox computes/transforms data only; the agent calls
  tools itself between `run_python` steps. Simplest, safest, covers most uses.
- **Option B (later):** a line-delimited JSON RPC over an extra pipe — child
  writes `{"call": name, "args": {...}}`, parent invokes the tool (with full
  scope enforcement) and writes the result back. Only if a real use-case needs
  in-script tool calls.

Decide A vs B explicitly in the PR; ~~default to **A**~~ — see update below.

> **UPDATE (2026-06-19) — Option A is NOT viable; Option B is required.**
> Verified against the code: the `run_python` tool (`core/assistant/tools/code.py:111`)
> injects a live `call` bridge — `extra_globals={'call': call, 'list_tools':
> list_tools, 'json': _json}` — and `core/agents/tests/test_sandbox.py` locks it
> with ~6 tests, including **scope enforcement** and **approval gating** on
> in-script `call("orders.cancel")`-style callbacks. Dropping the bridge (Option
> A) would delete a used, tested capability. So the subprocess migration MUST
> implement Option B: a line-delimited JSON-RPC bridge over an extra pipe where
> the **parent** invokes the tool (re-running the same scope/approval
> enforcement `code.py`'s `call` does today) and writes the result back. This
> makes D1 a larger, security-critical PR than the "default to A" framing
> implied — the parent-side `call` handler must preserve `enforce_policy` + the
> approval gate exactly, or the sandbox becomes a scope-escalation hole. Scope
> it as its own focused, adversarially-reviewed PR; do not bundle it.

## Reuse
The existing AST validator + `CURATED` builtins map (verbatim — this is the
proven layer). `core/agents/tests/test_sandbox.py` is the regression gate;
every existing test must still pass against the subprocess runner.

## Risks
- **Spawn cost** — a subprocess per `run_python` is ~10–30ms. Fine for an
  agent action (not a hot request path); note it.
- **Platform differences** — `os.killpg`/`setrlimit` are POSIX. Guard with
  capability checks; on Windows fall back to `proc.kill()` + a documented
  weaker guarantee (the deployment target is Linux containers, so this is the
  primary path).
- **Serialization** — only JSON-serializable results cross the boundary;
  document the constraint (today's in-process runner could return richer
  objects). Most `run_python` outputs are dict/list/scalar already.
- **Cold imports** — the child is a bare `python -m`; keep its imports minimal
  so spawn stays cheap.

## Verification
- Port `test_sandbox.py` to the subprocess runner — all existing behavior
  (allowed ops compute correctly; forbidden syntax/names rejected) green.
- New: `while True: pass` terminates within the timeout and leaves **no**
  surviving process (assert via pgid reaping); a CPU/memory bomb is killed by
  rlimit; non-JSON child output → clean sandbox error.
- Remove the leaked-thread counter + its tests once the subprocess path lands.
- `DATABASE_URL='sqlite:///:memory:'` (no DB needed; these are pure).
