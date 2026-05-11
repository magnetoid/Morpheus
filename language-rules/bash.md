# Bash / Shell Scripting — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify Bash/Shell scripts.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🐚 Shell Version & Standard

**Target: Bash 5.x / POSIX sh**

---

## ✅ Mandatory Rules

### 1. The Sacred Header — Always Required
Every single script must begin with this header:
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```
- `set -e`: Exit immediately if any command fails
- `set -u`: Treat unset variables as errors (prevents `rm -rf /$VAR` disasters)
- `set -o pipefail`: Pipes fail if any command in the pipe fails
- `IFS=$'\n\t'`: Safer word splitting

**Add to every Bash prompt:** *"Every script MUST start with `#!/usr/bin/env bash` and `set -euo pipefail`."*

### 2. Quote All Variable Expansions
```bash
# ❌ REJECT — vulnerable to word splitting and globbing
rm -rf $TARGET_DIR
for file in $FILES; do

# ✅ REQUIRE — always double-quote variables
rm -rf "${TARGET_DIR}"
for file in "${FILES[@]}"; do
```

### 3. Use `[[ ]]` Instead of `[ ]` for Conditionals
```bash
# ❌ REJECT — [ ] has edge cases
if [ "$var" == "value" ]; then

# ✅ REQUIRE — [[ ]] is safer and more powerful
if [[ "${var}" == "value" ]]; then
if [[ -f "${file}" ]]; then
if [[ -z "${var:-}" ]]; then
```

### 4. Use Parameter Expansion with Defaults
```bash
# ❌ REJECT — unset variable causes hard-to-debug failure
echo "Hello, ${NAME}"

# ✅ REQUIRE — provide defaults
echo "Hello, ${NAME:-World}"
readonly OUTPUT_DIR="${OUTPUT_DIR:-/tmp/output}"
```

### 5. Validate Required Variables Early
```bash
# ✅ Check for required environment variables at the top of the script
check_required_vars() {
    local required_vars=("DATABASE_URL" "API_KEY" "ENVIRONMENT")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            echo "ERROR: Required variable '${var}' is not set." >&2
            exit 1
        fi
    done
}
check_required_vars
```

### 6. Use Functions for Reusable Logic
```bash
# ✅ Organize scripts with named functions
log_info() { echo "[INFO] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >&2; }
log_error() { echo "[ERROR] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >&2; }

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -rf "${TEMP_DIR:-}" 2>/dev/null || true
}
trap cleanup EXIT
```

### 7. Use `trap` for Cleanup on Exit
```bash
# ✅ Always clean up temp files even if the script fails
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_DIR}"' EXIT

# Now safely use TEMP_DIR knowing it will be cleaned up
```

### 8. Never Use `eval` with User Input
```bash
# ❌ REJECT — arbitrary code execution
eval "command_${USER_INPUT}"

# ✅ REQUIRE — whitelist-based approach
case "${USER_INPUT}" in
    start|stop|restart)
        "${USER_INPUT}_service"
        ;;
    *)
        log_error "Invalid command: ${USER_INPUT}"
        exit 1
        ;;
esac
```

---

## 🚫 AI Pitfalls to Watch for in Bash

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| Missing `set -euo pipefail` | No safety flags in header | Add immediately after shebang |
| Unquoted variables | `$VAR` without quotes | Always `"${VAR}"` |
| Using `[ ]` | Single brackets in conditions | Replace with `[[ ]]` |
| `eval` with user input | `eval "$USER_DATA"` | Use case/whitelist instead |
| No cleanup on error | Temp files not removed on failure | Add `trap cleanup EXIT` |
| Hard-coded paths | `/home/user/...` | Use variables with `${HOME}` |
| No input validation | Missing checks for empty args | Validate `$#` and required args |

---

## 📋 Prompt Template for Bash

```
You are a senior DevOps/SRE engineer writing production-grade Bash scripts.
Follow these rules EXACTLY:
- EVERY script starts with: #!/usr/bin/env bash and set -euo pipefail
- EVERY variable expansion must be double-quoted: "${VAR}"
- Use [[ ]] for all conditionals, never [ ]
- Use trap 'cleanup' EXIT for temporary file management
- Validate all required environment variables at script start
- Never use eval with external or user-provided input
- Use functions to organize logic into reusable, named blocks
- Use readonly for constants

TASK: [Your task here]
```
