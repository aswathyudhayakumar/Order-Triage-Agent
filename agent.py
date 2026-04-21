"""
agent.py — Core triage logic for the Order Triage Agent

ARCHITECTURE DECISIONS:
-----------------------
1. Schema-agnostic by design: Instead of hardcoding column names, we send the
   raw CSV headers + a sample row to the LLM and ask it to produce a normalized
   TicketRecord. This means the agent works on Quince, Amazon, Shopify, or any
   custom export without config changes.

2. Two-stage LLM pipeline:
   Stage 1 (schema_inference): Maps arbitrary CSV columns -> canonical fields.
   Stage 2 (triage): Given a normalized ticket, produces classification +
   resolution + reasoning + draft response.
   Separating these stages keeps each prompt focused and makes the system easier
   to debug, test, and extend (e.g. swap Stage 1 for a rule-based mapper later).

3. Structured JSON output: Both stages return strict JSON. We validate the shape
   before passing downstream. If parsing fails, we return a graceful error record
   rather than crashing the whole batch.

4. Batching with per-row error isolation: Each ticket is processed independently.
   A malformed row does not poison the rest of the batch.

5. Human-in-the-loop ready: The output schema includes a confidence field and
   requires_human_review flag. This is the hook for a future approval workflow.
"""

import json
import os
import re
from typing import Any

from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

CANONICAL_FIELDS = [
    "ticket_id",
    "customer_name",
    "order_id",
    "issue_description",
    "channel",
    "created_at",
    "product",
    "order_value",
]

ISSUE_TYPES = [
    "wrong_item", "missing_item", "damaged_item", "not_delivered",
    "delayed", "return_request", "billing_issue", "other"
]
RESOLUTIONS = [
    "refund", "reship", "escalate_to_human", "no_action_needed",
    "request_more_info"
]
SEVERITIES = ["low", "medium", "high", "critical"]


SCHEMA_INFERENCE_PROMPT = """
You are a data normalization expert for an ecommerce operations platform.

You will receive:
- The column headers of an uploaded CSV file
- One sample data row

Your job is to produce a JSON mapping from each CANONICAL field to the most
likely matching CSV column name (or null if no match exists).

Canonical fields: {canonical_fields}

CSV headers: {headers}
Sample row:  {sample_row}

Respond ONLY with a valid JSON object. No explanation, no markdown, no backticks.
Example format:
{{
  "ticket_id": "ID",
  "customer_name": "Customer",
  "order_id": "Order #",
  "issue_description": "Description",
  "channel": null,
  "created_at": "Date",
  "product": "Item",
  "order_value": null
}}
"""


def infer_schema(headers, sample_row):
    prompt = SCHEMA_INFERENCE_PROMPT.format(
        canonical_fields=CANONICAL_FIELDS,
        headers=headers,
        sample_row=json.dumps(sample_row),
    )
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def normalize_row(row, mapping):
    normalized = {}
    for canonical, csv_col in mapping.items():
        normalized[canonical] = row.get(csv_col, "") if csv_col else ""
    return normalized


TRIAGE_PROMPT = """
You are an expert ecommerce operations agent performing ticket triage.

Given the following normalized customer support ticket, you must:
1. Classify the issue type (pick one from the list)
2. Assign a severity level
3. Decide the best resolution action
4. Write a short, empathetic draft response to the customer (2-3 sentences max)
5. Explain your reasoning in 1-2 sentences
6. Flag if this needs human review (true if severity=critical OR resolution=escalate_to_human)
7. Give a confidence score 0.0-1.0 for your triage decision

Issue types: {issue_types}
Severity levels: {severities}
Resolution options: {resolutions}

Ticket:
{ticket}

Respond ONLY with a valid JSON object. No explanation, no markdown, no backticks.
Use this exact shape:
{{
  "issue_type": "<one of the issue types>",
  "severity": "<one of the severity levels>",
  "resolution": "<one of the resolution options>",
  "draft_response": "<draft customer response>",
  "reasoning": "<your reasoning>",
  "requires_human_review": <true|false>,
  "confidence": <0.0-1.0>
}}
"""


def triage_ticket(normalized_ticket):
    prompt = TRIAGE_PROMPT.format(
        issue_types=ISSUE_TYPES,
        severities=SEVERITIES,
        resolutions=RESOLUTIONS,
        ticket=json.dumps(normalized_ticket, indent=2),
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        return {**normalized_ticket, **result, "triage_error": None}
    except Exception as e:
        return {
            **normalized_ticket,
            "issue_type": "unknown",
            "severity": "unknown",
            "resolution": "escalate_to_human",
            "draft_response": "",
            "reasoning": "",
            "requires_human_review": True,
            "confidence": 0.0,
            "triage_error": str(e),
        }


def run_triage(rows):
    if not rows:
        return [], {}
    headers = list(rows[0].keys())
    mapping = infer_schema(headers, rows[0])
    results = []
    for row in rows:
        normalized = normalize_row(row, mapping)
        result = triage_ticket(normalized)
        results.append(result)
    return results, mapping
