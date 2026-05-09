# Comprehensive Code Analysis Report

## 1. Security Vulnerabilities

### 1.1 Server-Side Request Forgery (SSRF) in AI Probe Service
**Location:** `plugins/installed/ai_assistant/services/probe.py:35`
**Severity:** HIGH
**Impact:** The `base_url` parameter can be controlled by the user. Using `urllib.request.urlopen` without validating the URL scheme allows an attacker to supply `file:///etc/passwd` or internal network IPs (e.g., AWS metadata `http://169.254.169.254/`). This could lead to sensitive data exposure.
**Recommended Fix:** Validate the URL scheme before making the request. Ensure the URL starts strictly with `http://` or `https://`.
**Test Case:** 
```python
def test_probe_rejects_file_scheme():
    result = probe_openai(api_key="test", base_url="file:///etc/passwd")
    assert result['ok'] is False
    assert "Invalid scheme" in result['error']
```

### 1.2 Remote Code Execution (RCE) Risks via `exec()`
**Location:** `plugins/installed/functions/runtime.py:243`
**Severity:** HIGH
**Impact:** The application uses `exec()` to run merchant-provided Python code. Although it restricts globals and validates the AST, `exec()` is notoriously difficult to secure against determined attackers who might exploit Python's introspection capabilities to escape the sandbox.
**Recommended Fix:** Replace the thread-based `exec()` sandbox with a robust isolation mechanism such as WebAssembly (WASM), a secure subprocess runner, or gVisor.
**Test Case:**
```python
def test_sandbox_blocks_introspection():
    source = "def run(input): return ().__class__.__base__.__subclasses__()"
    with pytest.raises(FunctionError):
        execute(source=source)
```

### 1.3 Insecure Temporary Directory Creation
**Location:** 
- `core/assistant/persistence.py:29-35`
- `core/management/commands/morph_backup.py:36`
**Severity:** MEDIUM
**Impact:** Fallback storage and backup directories are created in predictable, shared locations (`/tmp/morpheus-assistant` and `/tmp/morpheus-backups`). On shared environments, local attackers could read sensitive database backups or launch symbolic link attacks.
**Recommended Fix:** Use `tempfile.gettempdir()` combined with dynamically generated paths (e.g., `tempfile.mkdtemp()`) or store files securely within the application's restricted data directory.
**Test Case:** Run the backup command and verify the backup is written to a non-predictable directory with `0700` permissions.

### 1.4 Weak Cryptographic Hash (MD5)
**Location:** `core/utils/cache.py:20`
**Severity:** LOW
**Impact:** MD5 is used to generate cache keys. While not used for password hashing, environments with strict FIPS compliance enabled will crash when MD5 is invoked.
**Recommended Fix:** Change to `hashlib.md5(..., usedforsecurity=False).hexdigest()` or use `hashlib.sha256()`.
**Test Case:** Enable FIPS mode in the Python environment and verify that `cache_graphql_query` does not raise a `ValueError`.

### 1.5 Potential Cross-Site Scripting (XSS)
**Location:** `plugins/installed/cms/templatetags/cms.py`, `plugins/installed/seo/templatetags/seo.py`
**Severity:** MEDIUM
**Impact:** Extensive use of `mark_safe()` in template tags. If user-generated content is passed to these tags without prior HTML escaping, it could execute arbitrary JavaScript in the user's browser.
**Recommended Fix:** Ensure all user inputs are passed through `django.utils.html.escape()` before concatenating into the string that is marked safe.
**Test Case:** Pass `<script>alert(1)</script>` as a payload to the CMS block and verify the output HTML is safely escaped.

---

## 2. Logical Errors & Inconsistencies

### 2.1 Swallowed Exceptions (Empty Except Blocks)
**Location:** Across the codebase (e.g., `api/exception_handler.py:52`, `core/tasks.py:137`)
**Severity:** MEDIUM
**Impact:** Broad `except Exception: pass` blocks (annotated with `# noqa: BLE001`) suppress errors silently. While intended for graceful degradation, it prevents error tracking via the OpenTelemetry stack.
**Recommended Fix:** Log the exception using `logger.warning("Error description", exc_info=True)` before passing, ensuring the error is recorded without breaking the user experience.
**Test Case:** Trigger a known failure in an optional plugin and verify a warning is emitted to the logs.

### 2.2 Hardcoded Data & TODOs
**Location:** `plugins/installed/storefront/views.py:618`
**Severity:** LOW
**Impact:** Journal entries are currently hardcoded, preventing merchants from updating blog content via the CMS interface.
**Recommended Fix:** Implement the TODO by extracting the hardcoded entries into the CMS plugin data model.
**Test Case:** Ensure the storefront journal view queries the CMS model rather than returning static dictionaries.

---

## 3. Performance Issues

### 3.1 N+1 Query Problems (Database Performance)
**Location:** `core/assistant/tools/database.py:76` (and various views)
**Severity:** MEDIUM
**Impact:** Accessing related models (e.g., `getattr(o.customer, 'email', '')`) inside a loop over `Order.objects.all()` causes a separate database query for each iteration.
**Recommended Fix:** Add `.select_related('customer')` or `.prefetch_related()` to the initial QuerySet.
**Test Case:**
```python
def test_recent_orders_queries():
    with CaptureQueriesContext(connection) as queries:
        recent_orders_tool(limit=10)
    # Ensure only 1 query is executed, not 11
    assert len(queries) == 1
```

### 3.2 Thread Leak in Function Runtime
**Location:** `plugins/installed/functions/runtime.py:205`
**Severity:** HIGH
**Impact:** The `execute()` function uses `threading.Thread` to enforce timeouts. Python threads cannot be forcefully killed. If the executed code enters an infinite loop, the thread will hang indefinitely, eventually exhausting system resources.
**Recommended Fix:** Migrate the sandbox to a separate subprocess using `multiprocessing`, which can be forcefully terminated (`SIGKILL`) when the timeout is reached.
**Test Case:** Execute `while True: pass` in the function runtime and assert that the thread/process is fully reclaimed after the timeout.

---

## 4. Dependency Compatibility Checks

**Location:** `requirements.txt`
**Analysis:** The project relies on `django>=6.0`, `celery>=5.6`, and `opentelemetry-api>=1.27`.
**Impact:** Using `>=` for dependencies can lead to non-reproducible builds and unexpected breakages if a breaking major version is released upstream.
**Recommended Fix:** Pin dependencies exactly in a `requirements.txt` or `poetry.lock` for reproducible builds.
**Test Case:** Build the Docker image in a clean CI pipeline and verify all tests pass with the exact pinned dependency versions.