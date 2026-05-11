# Python — Vibe Coding Rules (2026)

> Apply these rules whenever asking any AI to generate, review, or modify Python code.
>
> **See also:** [../docs/universal-principles.md](../docs/universal-principles.md) (the 9 pillars), [../docs/workflow-guide.md](../docs/workflow-guide.md) (the loop), [../AGENTS.md](../AGENTS.md) (the protocols).

---

## 🐍 Python Version & Standard

**Target: Python 3.12+**
Always specify the Python version in your prompt. This prevents the AI from generating deprecated syntax.

```
# Add to every Python prompt:
"Use Python 3.12+ syntax. Follow PEP 8 and PEP 257."
```

---

## ✅ Mandatory Rules

### 1. Always Use Type Hints
AI must generate fully annotated function signatures. No bare `def` without types.
```python
# ❌ REJECT this
def process_user(user, db):
    pass

# ✅ REQUIRE this
def process_user(user: User, db: AsyncSession) -> UserResult:
    pass
```

### 2. Use Pydantic for Data Validation
All data models must use Pydantic v2 (not dataclasses or raw dicts for API contracts).
```python
from pydantic import BaseModel, EmailStr, field_validator

class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    age: int

    @field_validator('age')
    @classmethod
    def age_must_be_valid(cls, v: int) -> int:
        if v < 0 or v > 150:
            raise ValueError('Age must be between 0 and 150')
        return v
```

### 3. Async/Await for All I/O
All database operations, HTTP calls, and file I/O must use `asyncio`.
```python
# ❌ REJECT blocking I/O in async contexts
def get_user(user_id: str) -> User:
    return db.query(User).filter(User.id == user_id).first()

# ✅ REQUIRE async
async def get_user(user_id: str, session: AsyncSession) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

### 4. Explicit Error Handling (No Bare Except)
```python
# ❌ REJECT
try:
    result = await process()
except:
    pass

# ✅ REQUIRE
try:
    result = await process()
except DatabaseError as e:
    logger.error("Database error during process", exc_info=e)
    raise ServiceError("Processing failed") from e
```

### 5. Environment Variables for All Configuration
```python
# ❌ REJECT hardcoded secrets
DATABASE_URL = "postgresql://user:password@localhost/mydb"

# ✅ REQUIRE
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 6. Dependency Injection Pattern for Services
```python
# ✅ FastAPI dependency injection
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/users/{user_id}")
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    ...
```

---

## 🚫 AI Pitfalls to Watch for in Python

| Pitfall | What to Look For | How to Fix |
|---------|-----------------|------------|
| Hallucinated methods | `.filter_by()` on SQLAlchemy 2.0 async sessions | Use `select()` + `where()` |
| Missing `await` | `session.execute(...)` without `await` | Always `await` coroutines |
| Mutable default args | `def f(items=[])` | Use `def f(items: list = None)` |
| Bare `except` | `except:` with no exception type | Catch specific exceptions |
| Sync in async context | `time.sleep()` in async functions | Use `asyncio.sleep()` |
| Outdated imports | `from pydantic import validator` (v1) | Use `field_validator` (v2) |

---

## 📋 Prompt Template for Python

```
You are a senior Python engineer. Write Python 3.12+ code following these rules:
- Full type hints on all functions and variables
- Pydantic v2 for all data models
- asyncio for all I/O operations
- Explicit exception handling (no bare except)
- Environment variables for all configuration (pydantic-settings)
- PEP 8 and PEP 257 compliance
- No global mutable state

TASK: [Your task here]
```
