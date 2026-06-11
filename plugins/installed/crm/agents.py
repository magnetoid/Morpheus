"""CRM-specific agents."""

from __future__ import annotations

from core.agents import MorpheusAgent, Prompt, prompt_registry

prompt_registry.register(
    Prompt(
        name='account_manager',
        version=1,
        template=(
            'You are the Account Manager agent for an independent bookstore. '
            'You help the merchant maintain customer relationships: summarising '
            "a customer's history, surfacing follow-up actions, drafting outreach, "
            'and updating CRM records. When asked about a person, always check '
            'the timeline first via `crm.customer_timeline`. When you take a '
            'CRM action (logging an interaction, creating a lead), call the '
            'corresponding tool. Be terse and action-oriented.'
        ),
    )
)


class AccountManagerAgent(MorpheusAgent):
    name = 'account_manager'
    label = 'Account Manager'
    description = 'Summarises customer history, suggests follow-ups, drafts outreach.'
    icon = 'user-round'
    audience = 'merchant'
    scopes = [
        'catalog.read',
        'orders.read',
        'analytics.read',
        'crm.read',
        'crm.write',
        'content.read',
        'content.write',
    ]
    prompt_name = 'account_manager'
    temperature = 0.3
    max_tokens = 1200
    max_steps = 8
