Your task is to extract structured metadata from a rough feature
description.
Output ONLY valid JSON. No preamble. No code fences.

Extract use case metadata from:

"{idea}"

Respond with exactly:
{
  "title": "<3-5 word use case title — verb + noun only.
             RULE: Never more than 5 words. Never a full sentence.
             Never starts with 'The'. Always starts with a verb.
             Derive from the actual input domain — never default
             to booking or healthcare language.
             GOOD across domains:
               'Book Appointment'      (booking domain)
               'Process Payment'       (finance domain)
               'Monitor Competitor Prices' (AI agent domain)
               'Submit Subsidy Claim'  (agriculture domain)
               'Pick Warehouse Order'  (logistics domain)
             BAD:
               'Reserve an Available Slot with a Preferred Provider'
               'The System Allows a User to Complete the Action'>",

  "goal_level": "<ALMOST ALWAYS 'user_goal' — default to this unless:
    - spans multiple sessions or multiple actors completing
      separate tasks → use 'summary'
    - single step INSIDE another use case → use 'subfunction'
    If in doubt: use 'user_goal'.>",

  "actor": "<Primary role initiating this use case.
             Use the actor specified in the input if one is provided.
             Only infer if none is specified.
             Must be a role name, never a person name.
             Derive from the actual domain:
               Booking: 'Patient', 'Guest', 'Customer'
               Logistics: 'Warehouse Picker', 'Driver', 'Dispatcher'
               AI agent: 'AI Agent', 'Monitoring Agent'
               Finance: 'Accountant', 'Customer', 'Approver'
               AgTech: 'Farmer', 'Agronomist'>",

  "supporting_actors": ["<external system or role this use case
                          calls — derive from input domain>"],

  "stakeholders": [
    {
      "name": "<stakeholder name — derive from input domain>",
      "interest": "<one sentence: what they need from this use case>"
    }
  ],

  "domain": "<business domain derived from input — e.g. healthcare,
              e-commerce, logistics, agriculture, finance, SaaS,
              AI automation — never default to healthcare>",

  "system_boundary": "<owning service or component — derive from
                       input domain, or null if unclear>",

  "trigger": "<specific event that starts this use case — derive
               from input, not from a booking template>",

  "goal": "<one sentence: what the actor achieves — specific to
            this domain and input>",

  "related_entities": ["<noun likely to be a database table —
                         derive from input domain>"],

  "scale_hints": {
    "frequency": "<estimated frequency derived from domain context
                   or null — e.g. '~500K writes/sec' for real-time
                   location, '~50/day' for clinic bookings,
                   'every 6 hours' for scheduled agents>",
    "concurrent_users": "<concurrent user estimate or null>",
    "data_volume": "<data volume estimate or null>"
  }
}
