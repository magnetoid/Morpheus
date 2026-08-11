# Morpheus CMS — AI-First Vision (Deep Concepts)

> This document extends ARCHITECTURE.md with the deep AI-first design.
> Every concept here has a clear implementation path inside the plugin system.

---

## Why "AI-First" Is Not Just a Feature Flag

Most platforms bolt AI on as a feature: "AI product descriptions", "AI chatbot".
That is not what Morph is.

**Morpheus treats AI as infrastructure** — the same way it treats the database or the cache.
Every request, every event, every data model is designed assuming AI will participate.

The shift:
```
Traditional CMS:   Human → UI → Database → Response
Morph:             Human/Agent → Intent → AI Context → GraphQL → Response
                                    ↑
                             AI enriches every layer
```

---

## Concept 1 — The Intent Engine

> Instead of browsing a catalog, customers express intent. Morph resolves it.

**Traditional:** Customer searches "red sneakers" → keyword match → paginated list
**Morph:** Customer says "I need something comfortable for a 10km walk in the rain, budget €120" → Intent Engine parses intent, understands constraints (waterproof, walking, budget, EU sizing likely), ranks products semantically, assembles a curated response with explanation.

### Intent Resolution Pipeline

```
Raw input (text, voice, image, agent message)
  ↓
IntentParser (LLM call)
  → structured IntentObject {
      category_hints: ["footwear", "outdoor"],
      constraints: {waterproof: true, max_price: 120, currency: "EUR"},
      use_case: "walking in rain",
      sentiment: "practical, not fashion",
    }
  ↓
IntentRouter
  → if product_search → SemanticSearch(intent)
  → if bundle_request → DynamicAssembler(intent)
  → if question → RAG(intent, catalog)
  → if complaint → SupportAgent(intent)
  ↓
Response enriched with: matched products + AI explanation + alternatives
```

### GraphQL API

```graphql
query {
  resolveIntent(input: "comfortable waterproof shoes for rainy walks under €120") {
    intent {
      parsedConstraints
      confidenceScore
    }
    products { id name price explanation }
    explanation   # "I found 4 waterproof walking shoes in your budget..."
    followUpQuestions  # ["Do you prefer low-cut or ankle support?"]
  }
}
```

### Hook
```
hook: 'intent.resolved' → plugins can intercept and modify intent before resolution
hook: 'intent.no_results' → trigger: notify merchant, suggest related products
```

---

## Concept 2 — Agent Memory

> AI agents and customers have persistent, structured memory across sessions.

Every customer/agent interaction builds a memory graph. This is not just "purchase history" — it is semantic memory: preferences, constraints, life context, relationship with the store.

### AgentMemory Model

```python
class AgentMemory(models.Model):
    # Who this memory belongs to
    customer = models.ForeignKey(Customer, null=True)  # human customer
    agent_id = models.CharField(max_length=200)        # external AI agent ID

    memory_type = models.CharField(choices=[
        ('preference', 'Preference'),      # "prefers dark colors", "vegan products only"
        ('constraint', 'Constraint'),      # "allergic to latex", "budget always <€200"
        ('context', 'Context'),            # "buying for a 6-year-old daughter"
        ('relationship', 'Relationship'),  # "loyal customer since 2024, 18 orders"
        ('feedback', 'Feedback'),          # "said shipping was too slow last time"
    ])

    key = models.CharField(max_length=200)  # e.g. "preferred_size", "dietary_restriction"
    value = models.JSONField()              # {"size": "XL"} | {"restriction": "gluten-free"}
    confidence = models.FloatField(default=1.0)  # 0.0–1.0, decays over time
    source = models.CharField(choices=[
        ('explicit', 'Customer stated it'),
        ('inferred', 'Inferred from behavior'),
        ('agent', 'Set by AI agent'),
    ])
    expires_at = models.DateTimeField(null=True)  # some memories decay
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Memory in GraphQL Context

Every authenticated request automatically loads the customer's memory and injects it into the AI context:

```python
# The memory becomes part of every LLM prompt:
system_prompt = f"""
You are a shopping assistant for {store.name}.

Customer memory:
- Prefers: {memory.get('preferences')}
- Constraints: {memory.get('constraints')}
- Last purchase: {memory.get('last_order_summary')}
- Relationship: {memory.get('relationship_tier')} customer, {order_count} orders

Always personalize recommendations using this context.
"""
```

---

## Concept 3 — Autonomous Store Operator (Merchant AI Co-Pilot)

> An AI that runs the merchant's business alongside them, proactively.

This is not a dashboard. This is an agent that **acts** and **alerts**.

### Autonomous Actions (with merchant approval gates)

| Trigger | AI Action | Approval Required? |
|---|---|---|
| Stock of SKU-123 drops below reorder point | Draft purchase order, notify supplier | Yes (one click) |
| Competitor price drop detected (via plugin) | Suggest price adjustment | Yes |
| Product has 0 sales in 30 days | Draft markdown campaign | Yes |
| 5-star review posted | Draft social media post | Yes |
| Abandoned cart spike detected | Generate recovery email variant | Auto if configured |
| Product description has < 50 words | Auto-generate full description | Auto if configured |
| New product uploaded with no images | Alert merchant, suggest stock photos | Alert only |
| Conversion rate drops 20% week-over-week | Diagnose funnel, generate report | Alert + report |
| Traffic spikes causing NATS event lag | Auto-scale Kubernetes Workers via GitOps PR | Auto (Ops Agent) |

### GitOps Ops-Agent

The Morpheus Ops-Agent acts as an autonomous SRE. It reads metrics from Prometheus (e.g., HTTP duration, NATS queue depth) and, instead of just sending an alert, uses the GitHub API to author a GitOps Pull Request. 

For instance, if `morpheus-web` needs more replicas, the Ops Agent:
1. Creates a new branch.
2. Modifies the `replicas: X` value in `k8s/deployment-web.yaml`.
3. Opens a PR against `main` for the team to review, effectively tying auto-scaling into the Git history.

### MerchantInsight Model

```python
class MerchantInsight(models.Model):
    insight_type = models.CharField(choices=[
        ('opportunity', 'Revenue Opportunity'),
        ('risk', 'Risk / Alert'),
        ('action', 'Suggested Action'),
        ('report', 'Automated Report'),
    ])
    priority = models.CharField(choices=[('critical','Critical'),('high','High'),('low','Low')])
    title = models.CharField(max_length=200)
    body = models.TextField()          # AI-generated explanation
    suggested_action = models.JSONField()  # structured action the merchant can approve
    is_approved = models.BooleanField(null=True)  # None=pending, True=approved, False=rejected
    ai_executed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

### GraphQL

```graphql
query {
  merchantInsights(priority: HIGH, unread: true) {
    id title body priority
    suggestedAction { type payload }
  }
}

mutation {
  approveMerchantAction(insightId: "...", approved: true) {
    success executionResult
  }
}
```

---

## Concept 4 — Dynamic Product Assembly

> AI assembles products that don't exist yet, on the fly, from intent.

**Example:** Customer says "I need a complete home office setup for under $500."
Morph doesn't just search. It **assembles** a bundle:
- Queries the catalog semantically
- Reasons about compatibility (monitor + stand + cable)
- Respects the budget constraint
- Returns a dynamic "Virtual Bundle" with a single add-to-cart action

```graphql
mutation {
  assembleBundle(
    intent: "complete home office setup under $500"
    constraints: { maxTotal: 500, currency: "USD" }
  ) {
    bundle {
      items { product { id name price } quantity reason }
      totalPrice
      explanation
      savings  # vs buying separately
    }
    alternatives { ... }  # 3 other bundle options
  }
}
```

Virtual bundles are ephemeral (not saved to DB) unless the customer adds them to cart, at which point they become a `CartBundle`.

---

## Concept 5 — Agent-to-Agent Commerce (A2A Protocol)

> AI agents from other systems can autonomously browse and purchase.

Morpheus exposes a structured **Agent Commerce Protocol** — a standard way for external AI agents (OpenAI Assistants, Claude tools, custom agents) to interact with the store.

This is secured natively by the `AgentAuthMiddleware`. The middleware intercepts `/graphql/agent/` requests, extracts the JWT Bearer token, validates the agent's scopes, and attaches an `AgentProfile` to the `request` context before GraphQL execution.

### Agent Registration

```graphql
mutation {
  registerAgent(
    agentId: "assistant-abc123"
    ownerEmail: "user@example.com"
    capabilities: { canPurchase: true, budgetLimit: { amount: 500, currency: "USD" } }
    allowedCategories: ["electronics", "office"]
  ) {
    agentToken  # scoped JWT for this agent
    agentProfile { id capabilities }
  }
}
```

### Agent Capabilities as LLM Tools

Morpheus auto-generates an **OpenAI-compatible tool manifest** and an **Anthropic tool schema** from the GraphQL schema. Any LLM can import these and immediately have shopping capabilities:

```json
// GET /api/agent-tools/openai-manifest.json
{
  "tools": [
    {
      "name": "search_products",
      "description": "Search for products by natural language query",
      "parameters": { "query": "string", "maxPrice": "number", "currency": "string" }
    },
    {
      "name": "add_to_cart",
      "description": "Add a product to the shopping cart",
      "parameters": { "productId": "string", "quantity": "integer" }
    },
    {
      "name": "checkout",
      "description": "Complete purchase of items in cart",
      "parameters": { "shippingAddress": "object", "paymentMethod": "string" }
    }
  ]
}
```

### Receipt as Structured Data

Agent receipts return machine-readable structured data (not HTML emails):

```json
{
  "order": {
    "id": "MRP00012345",
    "items": [{"sku": "DESK-01", "qty": 1, "price": {"amount": 299.99, "currency": "USD"}}],
    "total": {"amount": 329.99, "currency": "USD"},
    "tracking": {"carrier": "FedEx", "number": "...", "estimatedDelivery": "2026-04-30"}
  }
}
```

---

## Concept 6 — Predictive Commerce

> Morph acts before customers act.

### Pre-Staged Personalized Pages

At off-peak hours, Morph's Celery workers pre-generate personalized product pages, bundles, and recommendations for high-value customers. When they visit, there's zero latency — the page is already computed and cached.

### Demand Forecasting

```python
class DemandForecast(models.Model):
    product_variant = models.ForeignKey(ProductVariant)
    forecast_date = models.DateField()
    predicted_units = models.IntegerField()
    confidence_interval_low = models.IntegerField()
    confidence_interval_high = models.IntegerField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
```

Forecasts feed directly into reorder alerts (Concept 3) and pre-staging logic.

### Pre-Emptive Cart

For repeat customers: "You usually order X every 30 days. It's been 28 days. Pre-fill your cart?" → One tap checkout. The cart is already built.

---

## Concept 7 — AI Experiment Framework

> Every AI-generated piece of content is A/B testable. Prompts are code.

### PromptRegistry

Prompts are versioned, named, and stored in the DB. Never hardcoded.

```python
class PromptTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # e.g. "product_description_generator", "cart_recovery_email", "intent_parser"
    version = models.PositiveIntegerField()
    template = models.TextField()       # Jinja2 template with variables
    model_override = models.CharField(max_length=100, blank=True)  # use specific model
    temperature = models.FloatField(default=0.7)
    is_active = models.BooleanField(default=True)
    performance_score = models.FloatField(null=True)  # updated by experiment framework
    created_at = models.DateTimeField(auto_now_add=True)
```

### AIExperiment

```python
class AIExperiment(models.Model):
    name = models.CharField(max_length=200)
    prompt_a = models.ForeignKey(PromptTemplate, related_name='experiments_as_a')
    prompt_b = models.ForeignKey(PromptTemplate, related_name='experiments_as_b')
    metric = models.CharField(choices=[
        ('conversion_rate', 'Conversion Rate'),
        ('click_through', 'Click Through Rate'),
        ('cart_add', 'Add to Cart Rate'),
        ('revenue_per_session', 'Revenue Per Session'),
    ])
    traffic_split = models.FloatField(default=0.5)  # 0.5 = 50/50
    status = models.CharField(choices=[('running','Running'),('concluded','Concluded')])
    winner = models.ForeignKey(PromptTemplate, null=True, related_name='won_experiments')
    started_at = models.DateTimeField()
    concluded_at = models.DateTimeField(null=True)
```

When an experiment concludes, the winning prompt is automatically promoted to `is_active=True`.

---

## Concept 8 — Zero-Shot Catalog

> Merchants describe a product in plain language. Morph does everything else.

```graphql
mutation {
  zeroShotProduct(
    description: "Handmade ceramic coffee mug, holds 350ml, dishwasher safe, matte black glaze, made in Portugal"
    images: ["upload://img1.jpg"]
  ) {
    draft {
      name            # "Handmade Matte Black Ceramic Coffee Mug — 350ml"
      description     # Full SEO-optimized description
      shortDescription
      suggestedPrice { amount currency }
      suggestedCategory { id name }
      tags            # ["ceramic", "handmade", "coffee", "portugal", "matte"]
      metaTitle
      metaDescription
      attributes {    # extracted: material=ceramic, capacity=350ml, finish=matte
        attribute { name }
        values { name }
      }
    }
    confidence  # How confident the AI is in each field
    warnings    # ["Could not determine if food-safe certification applies"]
  }
}
```

The merchant reviews the draft and publishes in one click. Average time to publish: < 30 seconds.

---

## Concept 9 — Synthetic Customer Testing

> AI generates synthetic customers that stress-test the store automatically.

A background job (runs weekly or on deploy) spins up a set of synthetic customer personas and simulates their shopping journeys through the GraphQL API:

```python
SYNTHETIC_PERSONAS = [
    {"name": "Budget Buyer", "behavior": "always picks cheapest, abandons if shipping > 10%"},
    {"name": "Researcher", "behavior": "reads all reviews, visits product 3x before buying"},
    {"name": "Mobile Impulse", "behavior": "fast tap, abandons complex checkouts"},
    {"name": "Gift Buyer", "behavior": "searches by recipient type, needs gift wrapping"},
    {"name": "AI Agent", "behavior": "uses agentCheckout mutation, strict budget"},
]
```

Each persona runs through: search → product page → add to cart → checkout → payment.
Results are logged to `SyntheticTestRun` with: completion rate, drop-off points, errors encountered, time-to-checkout.

A regression alert fires if completion rate drops > 5% from baseline.

---

## Concept 10 — The AIContext Request Object

> AI enrichment is threaded through every GraphQL request automatically.

Every request to `/graphql/` gets an `AIContext` attached:

```python
@dataclass
class AIContext:
    customer_memory: list[AgentMemory]   # loaded from DB for auth'd users
    agent_capabilities: AgentCapabilities | None  # if agent token
    session_intent: str | None           # inferred from session history
    personalization_tier: str            # 'none' | 'basic' | 'full'
    experiment_assignments: dict         # {experiment_name: 'a' | 'b'}
    ab_test_cohort: str                  # for consistent experiment bucketing
```

GraphQL resolvers receive `AIContext` via Strawberry's `Info` object. Product queries automatically apply personalization if `personalization_tier == 'full'`.

---

## Implementation Path (AI Plugin Structure)

```
plugins/installed/ai_assistant/
├── app.py              # registers all AI GraphQL extensions + hooks
├── models.py              # AIInteraction, AgentMemory, PromptTemplate,
│                          # AIExperiment, MerchantInsight, DemandForecast
├── graphql/
│   ├── types.py           # AIContext, IntentResult, BundleAssembly, etc.
│   ├── queries.py         # resolveIntent, semanticSearch, merchantInsights
│   └── mutations.py       # assembleBundle, agentCheckout, zeroShotProduct,
│                          #   approveMerchantAction, registerAgent
├── services/
│   ├── llm.py             # Swappable gateway (OpenAI/Anthropic/Ollama)
│   ├── intent.py          # IntentParser + IntentRouter
│   ├── memory.py          # AgentMemory read/write/decay
│   ├── assembler.py       # DynamicProductAssembler
│   ├── embeddings.py      # Product vector embeddings
│   ├── rag.py             # RAG over product catalog
│   ├── recommendations.py
│   ├── forecasting.py     # DemandForecast
│   ├── operator.py        # AutonomousStoreOperator (insight generation)
│   └── zero_shot.py       # ZeroShotCatalogService
├── middleware.py           # Attaches AIContext to every request
├── tasks.py               # Celery: pre-stage pages, generate insights,
│                          #   run synthetic tests, decay memory confidence
├── agent_tools/
│   ├── openai_manifest.py  # Auto-generate OpenAI tool manifest from schema
│   └── anthropic_tools.py  # Auto-generate Anthropic tool schema
└── tests/
```

---

## The LLM Gateway (Swappable)

```python
# plugins/installed/ai_assistant/services/llm.py

class LLMGateway:
    """Abstract gateway — swap providers via StoreSettings."""

    @classmethod
    def from_settings(cls) -> 'LLMGateway':
        from core.models import StoreSettings
        provider = StoreSettings.get('ai_provider', 'openai')
        return {
            'openai': OpenAIGateway,
            'anthropic': AnthropicGateway,
            'ollama': OllamaGateway,       # local / private
            'plugin': PluginGateway,       # any plugin can register a custom LLM
        }[provider]()

    def complete(self, prompt: str, system: str = '', **kwargs) -> str: ...
    def embed(self, text: str) -> list[float]: ...
    def stream(self, prompt: str, system: str = '', **kwargs): ...

# Every call is automatically logged:
def complete(self, prompt, system='', **kwargs):
    result = self._raw_complete(prompt, system, **kwargs)
    AIInteraction.log(
        type='completion', model=self.model,
        prompt_tokens=count_tokens(prompt),
        completion_tokens=count_tokens(result),
        cost_usd=self._calculate_cost(...),
    )
    return result
```

---

## Key Design Rules for AI Layer

1. **AI never blocks a request** — all LLM calls that aren't user-initiated happen in Celery tasks
2. **Every AI output is explainable** — GraphQL always returns an `explanation` field alongside AI results
3. **Every AI action is reversible** — no autonomous action permanently changes data without an audit trail
4. **Memory has confidence decay** — old inferences lose confidence over time, preventing stale personalization
5. **Prompts are versioned assets** — never hardcode a prompt string; always use `PromptTemplate`
6. **Agents have explicit capability scopes** — no agent can do more than its registration allows
7. **Experiments are the default** — all new AI features launch as experiments, graduated by data
