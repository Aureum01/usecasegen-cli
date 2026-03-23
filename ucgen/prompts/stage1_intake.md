Your task is to extract structured metadata from a rough feature description.
Output ONLY valid JSON. No preamble. No code fences.

Extract use case metadata from:

"{idea}"

Respond with exactly:
{
  "title": "<descriptive use case title>",
  "goal_level": "<user_goal|summary|subfunction>",
  "actor": "<primary role - never a person name>",
  "supporting_actors": ["<system or role this use case calls>"],
  "stakeholders": [
    {"name": "<stakeholder>", "interest": "<one sentence: what they need>"}
  ],
  "domain": "<business domain>",
  "system_boundary": "<owning service or null>",
  "trigger": "<specific event that starts this>",
  "goal": "<one sentence: what actor achieves>",
  "related_entities": ["<noun1>", "<noun2>"],
  "scale_hints": {
    "frequency": "<estimated frequency or null>",
    "concurrent_users": "<concurrent user estimate or null>",
    "data_volume": "<data volume or null>"
  }
}
