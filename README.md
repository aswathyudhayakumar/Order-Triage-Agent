# Order Triage Agent

A schema-agnostic, AI-powered triage system for ecommerce customer support tickets. Upload any CSV -- Shopify, Zendesk, a custom export, whatever -- and the agent figures out your columns, classifies every ticket, picks a resolution, drafts a customer response, and flags anything that needs a human to look at it.

Built with Groq (Llama 3.3 70B) and Streamlit.

**[Live Demo](#)** · **[GitHub](https://github.com/YOUR_USERNAME/order-triage-agent)**

---

## Why I Built This

Customer support triage is one of those problems that looks simple from the outside and is quietly chaotic on the inside. At any ecommerce company handling real volume, hundreds of tickets come in daily -- wrong items, missing packages, billing errors, damaged goods. Someone has to read each one, figure out what happened, decide what to do, and write back to the customer.

Done manually, this is slow and inconsistent. Different agents make different calls on the same issue. Critical tickets get buried under low-priority ones. A lot of time gets spent on repetitive decisions that follow pretty predictable patterns.

I wanted to see how much of that could be automated -- not to remove humans from the loop entirely, but to handle the obvious cases automatically and surface the genuinely complex ones for review. That distinction felt important to get right.

---

## What It Does

- **Ingests any CSV format**: No configuration needed. The agent inspects your column headers and maps them to a standard schema automatically.
- **Classifies every ticket**: Issue type (wrong item, not delivered, billing issue, etc.) and severity (low to critical).
- **Recommends a resolution**: Refund, reship, escalate, request more info, or no action needed.
- **Drafts a customer response**: Short, empathetic, ready to send or edit.
- **Flags tickets for human review**: Anything critical or ambiguous gets surfaced -- the system knows its own limits.
- **Confidence scoring**: Every decision comes with a 0-1 score, which is the hook for downstream automation rules (e.g. auto-refund if confidence > 0.85 and order value < $50).

---

## How It Works

```
CSV Upload (any format)
        |
        v
Stage 1: Schema Inference (LLM)
Maps arbitrary column headers to canonical fields.
Runs once per batch, not per row.
        |
        v
Normalized TicketRecord
        |
        v
Stage 2: Triage (LLM, per ticket)
Classification + resolution + draft response.
Per-row error isolation -- one bad row does not crash the batch.
        |
        v
Output: Streamlit UI + downloadable CSV
Human-review queue surfaced automatically.
```

### Design Decisions Worth Explaining

**Two-stage pipeline instead of one big prompt**

Schema inference and triage are separated intentionally. Keeping each prompt small and focused makes the system easier to debug and easier to extend. It also means Stage 1 can be swapped for a rule-based mapper later without touching the triage logic at all -- same principle as a modular ETL pipeline.

**Schema-agnostic by design**

The agent does not expect a specific CSV format. Instead, it reads your headers and a sample row, then produces a mapping to a canonical internal schema. The canonical schema is the contract. Upstream formats are just adapters. This makes the tool portable across platforms without any configuration.

**Structured JSON output with enum-constrained fields**

Both LLM stages return typed JSON with fixed allowed values for severity, resolution, and issue type. This makes downstream processing reliable and opens the door to rule-based automation without brittle string parsing.

**Per-row error isolation**

Each ticket is processed independently. If one row fails -- malformed data, an API hiccup, an unexpected format -- it produces an error record flagged for human review rather than taking down the rest of the batch. Small thing, but important for anything running in production.

**Human-in-the-loop as a first-class output**

The requires_human_review flag and confidence score are explicit output fields, not afterthoughts. The goal is not full automation -- it is smart automation with a clear handoff for edge cases.

---

## Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/order-triage-agent
cd order-triage-agent
pip install -r requirements.txt
```

Create a `.env` file in the root:
```
GROQ_API_KEY=gsk_...
```

Run the app:
```bash
streamlit run app.py
```

Open `http://localhost:8501`, upload `sample_data/tickets.csv`, and click Run Triage.

Get a free Groq API key (no credit card) at [console.groq.com](https://console.groq.com).

---

## Sample Output

| Ticket | Issue Type | Severity | Resolution | Confidence | Human Review |
|--------|------------|----------|------------|------------|--------------|
| TKT-001 | wrong_item | medium | reship | 0.92 | No |
| TKT-002 | not_delivered | high | escalate_to_human | 0.78 | Yes |
| TKT-004 | billing_issue | critical | escalate_to_human | 0.95 | Yes |
| TKT-007 | damaged_item | high | refund | 0.91 | No |

---

## What's Next

- **Webhook intake**: Replace CSV upload with a real-time Zendesk or Gorgias webhook
- **Policy grounding**: Add a RAG layer so the agent reasons against actual return and refund policies
- **Auto-execute low-risk resolutions**: Integrate with an OMS API to trigger refunds automatically below a confidence and value threshold
- **Feedback loop**: Let ops agents mark decisions correct or incorrect to improve prompts over time

---

## Author

**Aswathy Udhaya Kumar** · [LinkedIn](https://www.linkedin.com/in/u-aswathy) · [Portfolio](https://aswathy-portfolio.framer.website/)
