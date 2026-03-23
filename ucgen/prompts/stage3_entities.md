Your task is to identify the database entities implied by this use case.
Output ONLY valid JSON. No preamble.

Extract database entities from:

Metadata: {intake_json}

Use case body summary: {sections_summary}

Respond with exactly:
{
  "entities": [
    {
      "name": "<PascalCase>",
      "fields": [
        {"name": "<snake_case>", "type": "<UUID|str|int|datetime|bool|decimal>", "constraints": ["<primary_key|foreign_key|not_null|unique|indexed>"]}
      ],
      "relationships": ["<belongs_to: EntityName>", "<has_many: EntityName>"]
    }
  ]
}
