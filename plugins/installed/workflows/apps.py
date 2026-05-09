"""
workflows — visual no-code automation, with agent-skill integration.

Shopify Flow lets merchants chain triggers + conditions + actions
without writing code. Morpheus's hook bus already broadcasts every
domain event (`order.placed`, `return.requested`, `product.low_stock`,
…) and the agent layer registers reusable Skill bundles. Workflows
sit between them: pick an event, define a condition, fire one or
more actions — including "invoke an agent skill". Shopify Flow can't
do that.

v1 ships:
  • `Workflow` model — name, trigger event, condition expression,
    actions list (JSON), is_active, run counters
  • `WorkflowRun` audit row per execution
  • Execution engine (`engine.run_for_event`) hooked into
    `core.hooks.hook_registry` for every registered trigger event
  • Conditions: a tiny safe expression evaluator over the event
    payload (no eval, just a recursive walker over a JSON-AST)
  • Actions: `notify_staff`, `tag_customer`, `add_order_note`,
    `webhook_post`, `agent_skill` (calls a registered Skill via the
    agent runtime)
  • Dashboard CRUD + JSON config editor (visual graph editor is v2)

Pure additive — no plugin needs to know workflows exist; everything
funnels through the existing hook bus.
"""
