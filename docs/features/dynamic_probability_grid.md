# Dynamic Book Grid & Probability Engine
**Module:** `dynamic_products`

## Overview
The Dynamic Book Grid application is an advanced feature of the `dynamic_products` plugin. It completely replaces static product carousels with a real-time, responsive, masonry-style grid layout where books are automatically prioritized based on their "Purchase Probability Score".

## 1. Purchase Probability Calculation Methodology
The algorithm computes a real-time propensity score (0.0 to 1.0) for every active book in the catalog. 
The calculation is orchestrated by the `calculate_grid_probabilities()` service.

### Factors & Weights
- **Historical Sales Data (`recent_sales_score` - Weight: 40%)**: Normalized sales volume over the last 30 days. Identifies proven converters.
- **User Browsing Popularity (`view_count_score` - Weight: 30%)**: Aggregate session views across the platform. Identifies high-interest items.
- **Trend Velocity (`trend_velocity` - Weight: 10%)**: The rate of change in views/sales over the last 48 hours. Identifies viral/trending books.
- **Inventory Levels (`inventory_score` - Multiplier)**: 
  - `1.0`: Healthy stock (>= 5 units)
  - `0.5`: Low stock (< 5 units) - penalizes slightly to avoid promoting items that will immediately sell out.
  - `0.0`: Out of stock - prevents out-of-stock items from appearing prominently.

**Formula:**
`Probability = ((Sales * 0.4) + (Popularity * 0.3) + (Trend * 0.1)) * Inventory_Multiplier`

Scores are capped between `0.0` and `1.0` and saved to the `DynamicGridItem` materialized view to ensure O(1) retrieval speed during storefront rendering.

## 2. Dynamic Grid Layout Logic
The frontend uses a CSS Grid architecture that natively reads the probability score attached to each product's `DynamicGridItem` record.

### Prominence Rules
- **High Probability (Score >= 0.8)**: Gets the `.prominence-high` class. Spans 2 columns and 2 rows. Features a larger cover image and larger typography.
- **Medium Probability (Score 0.5 - 0.79)**: Gets the `.prominence-medium` class. Spans 1 column and 2 rows. Standard typography but taller aspect ratio for visual hierarchy.
- **Low Probability (Score < 0.5)**: Gets the `.prominence-low` class. Spans 1 column and 1 row.

### Responsiveness
- **Desktop (>= 1024px)**: Auto-fill grid with `minmax(200px, 1fr)`. Full prominence rules applied.
- **Tablet (768px - 1024px)**: Falls back to a strict 2-column layout. High probability items span the full width (2 columns).
- **Mobile (< 480px)**: Single column list view (`1fr`). Prominence span rules are disabled to prevent horizontal scrolling, but vertical order (highest probability first) is strictly maintained.

## 3. Accessibility & Web Vitals
- **Accessibility**: 
  - The grid container has `role="list"` and items have `role="listitem"`.
  - The `aria-label` provides a screen-reader-friendly summary: `"{Title} by {Author} - {Price}"`.
  - Empty cover placeholders are marked `aria-hidden="true"`.
- **Performance**: 
  - All cover images include `loading="lazy"` and `decoding="async"`.
  - Explicit `width="400"` and `height="600"` attributes prevent Cumulative Layout Shift (CLS).