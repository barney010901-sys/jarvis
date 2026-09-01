Turn the user's request into an ordered list of concrete steps. Each step
should name the tool it needs (if any) from the tool registry below, or be
marked as a reasoning-only step.

Prefer the smallest plan that could plausibly satisfy the request. Mark any
step that would require a SENSITIVE tool explicitly, so the orchestrator
knows to request confirmation before running it.

Available tools:
{tool_list}

Request:
{request}

Relevant context:
{context}
