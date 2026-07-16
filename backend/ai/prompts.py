"""
Prompt construction for the AI Assistant.

Kept deterministic and reusable per AI_CONTEXT.md's "Prompt Philosophy"
(deterministic, structured, short, reusable — avoid conversational
prompts). The system prompt defines ERP Pulse's behaviour and never
changes per-request; the user prompt carries the per-request context and
question. Conversation history is NOT built here — it's threaded directly
into the provider's messages array (see AIProvider.generate_response),
since that's the shape providers actually expect for multi-turn context,
rather than flattened into this single string.
"""

import json

SYSTEM_PROMPT = (
    'You are ERP Pulse\'s Business Intelligence Assistant.\n\n'
    'Rules you must always follow:\n'
    '- Answer only using the business context provided to you in this conversation.\n'
    '- Never invent numbers, customers, products, or any other business data.\n'
    '- If NetSuite data is unavailable or the business context is empty, '
    'clearly say so instead of guessing.\n'
    '- Keep answers professional, concise, and grounded in the data you were given.\n'
    '- You are a Business Intelligence Assistant for this specific business, '
    'not a general-purpose chatbot.'
)


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_user_prompt(*, context: dict, message: str) -> str:
    """Combine business context and the user's question into one message for the provider."""
    if context.get('netsuite_connected'):
        field_notes = (
            'Field notes on the JSON below: `top_customers` ranks customers by '
            'outstanding AR balance (money owed to you), NOT revenue generated — '
            'use `top_customers_by_revenue` for revenue ranking instead. '
            '`revenue_this_month` covers the current calendar month. '
            '`revenue_this_fiscal_year` assumes an April-to-March fiscal year; '
            'if asked and you are not sure this matches the business\'s actual '
            'fiscal year configuration, say so rather than presenting it as certain.'
        )
        context_block = (
            f'{field_notes}\n\n'
            f'Business context: {json.dumps(context.get("business_context"), indent=2)}'
        )
    else:
        context_block = (
            'Business context: NetSuite is not connected for this account yet. '
            'No business data is available.'
        )

    return f'{context_block}\n\nUser question: {message}'