# Spec: Advanced Dynamic Storefront Engine (Morpheus Intent Engine)

## 1. Context & Current State
Currently, Morpheus OS provides dynamic product arrangement primarily through the `personalisation` plugin (`rank_for_visitor` and `pairs_with`). 
However, it has significant limitations for a true 2027 "Hyper-Personalized Storefront":
1. **Python-Level Sorting**: `rank_for_visitor` loads all candidate products and their embeddings into Python memory, calculates the centroid, and sorts. This works for a carousel of 12 items, but completely breaks down for a full catalog PLP (Product Listing Page) with pagination.
2. **Static Defaults**: The Home Page (`home.py`) fetches a static `featured: true` list via GraphQL. The Catalog (`catalog.py`) defaults to sorting by `-created_at`.
3. **Reactive, Not Predictive**: The system only reacts to recent views, rather than maintaining a persistent, predictive "User Intent Profile".

## 2. The Advanced Architecture (2027 Standard)
To ensure every person has a completely different arranged storefront, we must move personalization from the *application layer* (Python sorting) to the *database/vector layer* (pgvector), and expand it to the entire storefront layout.

### Pillar 1: Vector-Native Catalog Sorting (pgvector)
Instead of sorting in Python, we maintain a running `intent_vector` (the centroid of their views + purchases) for the user's session. 
We inject this vector directly into the Django ORM query using `pgvector`'s `<=>` (cosine distance) operator. This allows us to sort a 100,000-item catalog instantly and paginate it seamlessly.

### Pillar 2: Dynamic Home Page Generation
The Home Page will abandon static `featuredProducts`. Instead, it will fetch:
- **Hero Grid**: `Top K` products closest to the user's `intent_vector`.
- **Zero-Shot Fallback**: If the user is new (no vector), we use "Contextual Trending" (e.g., trending items for their geographic region or referral source).

### Pillar 3: Real-Time Intent Updating
A new middleware or Celery background task will update the `AnalyticsSession` with a compiled `intent_vector` every time a user views a product, adds to cart, or completes a purchase.

## 3. Implementation Plan (Atomic Chunks)

### Chunk 1: `UserIntent` Vector Storage
Add a `UserIntentVector` model linked to the `AnalyticsSession` (or user profile) to store the real-time calculated centroid of their interests.

### Chunk 2: Database-Level Sorting (`catalog.py`)
Modify `catalog.py` to support a new sort mode: `sort=for_you`. 
When active, it retrieves the user's `UserIntentVector` and orders the Django QuerySet using Postgres vector similarity. We will set `for_you` as the default sort if the user has a populated intent vector.

### Chunk 3: Dynamic Home Page (`home.py`)
Modify the `home.py` GraphQL query to accept an `intentVector` or `sessionToken` to return personalized featured products natively, replacing the static hardcoded list.

## 4. Expected Code Changes
- `plugins/installed/personalisation/models.py`: Add `SessionIntentVector`.
- `plugins/installed/personalisation/services.py`: Add logic to update the vector on product view.
- `plugins/installed/storefront/views/catalog.py`: Update the PLP to use DB-level vector sorting.
- `plugins/installed/storefront/views/home.py`: Update to fetch personalized hero products.
