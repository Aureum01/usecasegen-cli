Your task is to write the full body of a use case specification following Cockburn's fully dressed format.
Output ONLY valid JSON. No preamble. No code fences.

Write the use case body for:

{intake_json}

Respond with exactly:
{
  "preconditions": ["<verifiable state>"],
  "minimal_guarantee": "<what system promises even on failure>",
  "success_guarantee": "<what is true for all stakeholders after success>",
  "normal_course": [
    {"step": 1, "actor": "<Actor|System>", "action": "<present tense>", "system_response": "<response>"}
  ],
  "alternative_courses": [
    {"ref": "2a", "condition": "<trigger>", "response": "<what happens>"}
  ],
  "postconditions": ["<verifiable outcome>"],
  "information_requirements": [
    {"step": 1, "data_needed": "<what>", "source": "<table/service>", "format": "<type>"}
  ],
  "nfr": [
    {"type": "<latency|availability|consistency|throughput|compliance|security>", "requirement": "<req>", "threshold": "<measurable threshold or null>"}
  ],
  "state_machine": null,
  "open_issues": ["<question for stakeholders>"]
}
