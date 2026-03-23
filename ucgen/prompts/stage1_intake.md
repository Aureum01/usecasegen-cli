Your task is to extract structured metadata from a rough feature description.
Output ONLY valid JSON. No preamble. No code fences.

Extract use case metadata from:

"{idea}"

Respond with exactly:
{
  "title": "<3-5 word use case title — verb + noun only.
           GOOD: 'Book Appointment', 'Cancel Order', 'Reset Password',
                 'Process Payment', 'Check In Patient'
           BAD:  'Reserve an Available Slot with a Preferred Provider'
                 'The System Allows a Patient to Book'
           RULE: Never more than 5 words. Never a full sentence.
                 Never starts with 'The'. Always starts with a verb.>",
  "goal_level": "<ALMOST ALWAYS 'user_goal' — default to this unless:
  - The use case spans multiple sessions or multiple actors
    completing separate tasks → use 'summary'
  - The use case is a single step INSIDE another use case
    e.g. 'Validate Payment Card' inside 'Process Payment' → use 'subfunction'
  If in doubt: use 'user_goal'. Most use cases a developer
  would name and implement are user_goal level.>",
  "actor": "<Use the actor specified in the input if one is provided.
           Only infer the actor if none is specified.
           Actor must be a role name, never a person name.>",
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
