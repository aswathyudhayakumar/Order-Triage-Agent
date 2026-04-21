"""
app.py — Streamlit UI for the Order Triage Agent

Run with:  streamlit run app.py
"""

import io
import csv
import time
import pandas as pd
import streamlit as st

from agent import run_triage, ISSUE_TYPES, SEVERITIES, RESOLUTIONS

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Order Triage Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Dark industrial palette */
.stApp {
    background-color: #0f0f0f;
    color: #e8e4dc;
}

h1, h2, h3 {
    font-family: 'DM Mono', monospace !important;
    letter-spacing: -0.02em;
}

/* Severity badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 3px;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.badge-critical { background: #ff3b30; color: #fff; }
.badge-high     { background: #ff9500; color: #000; }
.badge-medium   { background: #ffd60a; color: #000; }
.badge-low      { background: #30d158; color: #000; }
.badge-unknown  { background: #636366; color: #fff; }

/* Resolution badges */
.res-refund             { background: #0a84ff22; color: #0a84ff; border: 1px solid #0a84ff55; }
.res-reship             { background: #30d15822; color: #30d158; border: 1px solid #30d15855; }
.res-escalate_to_human  { background: #ff375f22; color: #ff375f; border: 1px solid #ff375f55; }
.res-no_action_needed   { background: #63636622; color: #aeaeb2; border: 1px solid #63636655; }
.res-request_more_info  { background: #ffd60a22; color: #ffd60a; border: 1px solid #ffd60a55; }

/* Human review flag */
.review-flag {
    background: #ff375f;
    color: white;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.72rem;
    font-family: 'DM Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Reasoning block */
.reasoning-box {
    background: #1c1c1e;
    border-left: 3px solid #636366;
    padding: 10px 14px;
    border-radius: 0 4px 4px 0;
    font-size: 0.85rem;
    color: #aeaeb2;
    margin: 6px 0;
}

/* Draft response */
.draft-box {
    background: #1c1c1e;
    border-left: 3px solid #0a84ff;
    padding: 10px 14px;
    border-radius: 0 4px 4px 0;
    font-size: 0.85rem;
    color: #e8e4dc;
    font-style: italic;
    margin: 6px 0;
}

/* Confidence bar container */
.conf-bar-bg {
    background: #2c2c2e;
    border-radius: 4px;
    height: 6px;
    width: 100%;
    margin-top: 4px;
}
.conf-bar-fill {
    height: 6px;
    border-radius: 4px;
    background: linear-gradient(90deg, #0a84ff, #30d158);
}

/* Metric cards */
[data-testid="metric-container"] {
    background: #1c1c1e;
    border: 1px solid #2c2c2e;
    border-radius: 8px;
    padding: 16px;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    background: #1c1c1e;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #161616;
    border-right: 1px solid #2c2c2e;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #1c1c1e;
    border: 1px dashed #3a3a3c;
    border-radius: 8px;
}

/* Expander */
[data-testid="stExpander"] {
    background: #1c1c1e;
    border: 1px solid #2c2c2e;
    border-radius: 8px;
}

/* Button */
.stButton > button {
    background: #e8e4dc;
    color: #0f0f0f;
    border: none;
    font-family: 'DM Mono', monospace;
    font-weight: 500;
    letter-spacing: 0.03em;
    border-radius: 4px;
    padding: 10px 28px;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    background: #ffffff;
    transform: translateY(-1px);
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def severity_badge(sev: str) -> str:
    cls = f"badge badge-{sev.lower()}"
    return f'<span class="{cls}">{sev}</span>'

def resolution_badge(res: str) -> str:
    cls = f"badge res-{res.lower()}"
    label = res.replace("_", " ")
    return f'<span class="{cls}">{label}</span>'

def confidence_bar(score: float) -> str:
    pct = int(score * 100)
    return f"""
    <div style="font-family:'DM Mono',monospace;font-size:0.75rem;color:#636366">
        Confidence {pct}%
    </div>
    <div class="conf-bar-bg">
        <div class="conf-bar-fill" style="width:{pct}%"></div>
    </div>
    """

def results_to_csv(results: list[dict]) -> str:
    if not results:
        return ""
    fieldnames = list(results[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)
    return buf.getvalue()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## `ORDER TRIAGE`\n### `AGENT v1.0`")
    st.markdown("---")
    st.markdown("""
**How it works**

1. Upload any CSV of support tickets
2. Agent infers your schema automatically
3. Each ticket is classified, triaged, and gets a draft response
4. Download results or review flagged tickets

**Architecture**
- Stage 1 · Schema inference
- Stage 2 · Per-ticket triage
- Human-review flag on critical/escalations
    """)
    st.markdown("---")
    st.markdown("**Supported resolutions**")
    for r in RESOLUTIONS:
        st.markdown(f"- `{r}`")
    st.markdown("---")
    st.caption("Built with Claude API · Streamlit")


# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown("# 📦 Order Triage Agent")
st.markdown("Upload any customer support ticket CSV. The agent infers your schema, classifies every ticket, picks a resolution, and drafts a customer response.")

st.markdown("---")

# Sample data download
import os
_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_dir, "sample_data", "tickets.csv"), "r") as f:
    sample_csv = f.read()

col1, col2 = st.columns([3, 1])
with col1:
    uploaded = st.file_uploader(
        "Upload tickets CSV",
        type=["csv"],
        help="Any CSV format works — the agent will map your columns automatically."
    )
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        "⬇ Download sample CSV",
        data=sample_csv,
        file_name="sample_tickets.csv",
        mime="text/csv",
    )

if uploaded:
    df_raw = pd.read_csv(uploaded, quoting=csv.QUOTE_ALL, on_bad_lines='skip')
    st.markdown(f"**{len(df_raw)} tickets loaded** · Columns: `{'`, `'.join(df_raw.columns.tolist())}`")

    with st.expander("Preview raw data", expanded=False):
        st.dataframe(df_raw.head(5), use_container_width=True)

    if st.button("🚀 Run Triage"):
        rows = df_raw.to_dict(orient="records")

        progress = st.progress(0, text="Inferring schema...")
        status   = st.empty()

        # Stage 1 — schema inference (happens inside run_triage, first call)
        time.sleep(0.3)
        progress.progress(10, text="Schema mapped · Starting triage...")

        # Stage 2 — triage per row
        results = []
        schema_mapping = {}
        n = len(rows)

        # We'll call the pipeline row by row so we can update the progress bar
        from agent import infer_schema, normalize_row, triage_ticket

        headers = list(rows[0].keys())
        schema_mapping = infer_schema(headers, rows[0])

        with st.expander("🗺 Inferred schema mapping", expanded=True):
            mapping_df = pd.DataFrame([
                {"Canonical field": k, "Your CSV column": v or "— not found —"}
                for k, v in schema_mapping.items()
            ])
            st.dataframe(mapping_df, use_container_width=True)

        for i, row in enumerate(rows):
            normalized = normalize_row(row, schema_mapping)
            result     = triage_ticket(normalized)
            results.append(result)
            pct = int(10 + (i + 1) / n * 85)
            progress.progress(pct, text=f"Triaging ticket {i+1} of {n}…")

        progress.progress(100, text="Done ✓")
        status.success(f"✅ {n} tickets triaged successfully")

        st.session_state["results"] = results
        st.session_state["schema"]  = schema_mapping


# ── Results ───────────────────────────────────────────────────────────────────

if "results" in st.session_state:
    results = st.session_state["results"]

    st.markdown("---")
    st.markdown("## Results")

    # Summary metrics
    total     = len(results)
    critical  = sum(1 for r in results if r.get("severity") == "critical")
    escalated = sum(1 for r in results if r.get("requires_human_review"))
    refunds   = sum(1 for r in results if r.get("resolution") == "refund")
    reships   = sum(1 for r in results if r.get("resolution") == "reship")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total tickets",     total)
    m2.metric("🔴 Critical",        critical)
    m3.metric("👤 Needs review",    escalated)
    m4.metric("💰 Refunds",         refunds)
    m5.metric("📦 Reships",         reships)

    # Filter controls
    st.markdown("### Ticket Details")
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        sev_filter = st.multiselect("Filter by severity", SEVERITIES, default=[])
    with filter_col2:
        res_filter = st.multiselect("Filter by resolution", RESOLUTIONS, default=[])
    with filter_col3:
        review_only = st.checkbox("Show human-review flagged only", value=False)

    filtered = results
    if sev_filter:
        filtered = [r for r in filtered if r.get("severity") in sev_filter]
    if res_filter:
        filtered = [r for r in filtered if r.get("resolution") in res_filter]
    if review_only:
        filtered = [r for r in filtered if r.get("requires_human_review")]

    st.caption(f"Showing {len(filtered)} of {total} tickets")

    # Ticket cards
    for i, r in enumerate(filtered):
        sev = r.get("severity", "unknown")
        res = r.get("resolution", "unknown")
        tid = r.get("ticket_id") or r.get("order_id") or f"#{i+1}"
        customer = r.get("customer_name") or "Unknown customer"
        issue    = r.get("issue_description") or "—"
        issue_type = r.get("issue_type", "other").replace("_", " ")
        conf     = r.get("confidence", 0.0) or 0.0
        needs_review = r.get("requires_human_review", False)
        error    = r.get("triage_error")

        label = f"**{tid}** · {customer} · {issue_type.upper()}"
        if needs_review:
            label += "  🚨"

        with st.expander(label, expanded=(sev == "critical")):
            left, right = st.columns([3, 2])

            with left:
                st.markdown(f"**Issue:** {issue[:200]}")
                if r.get("product"):
                    st.markdown(f"**Product:** {r['product']}")
                if r.get("order_id"):
                    st.markdown(f"**Order:** `{r['order_id']}`")
                if r.get("created_at"):
                    st.markdown(f"**Submitted:** {r['created_at']}")

                st.markdown(
                    f"{severity_badge(sev)} &nbsp; {resolution_badge(res)}"
                    + ("&nbsp; &nbsp; <span class='review-flag'>⚠ human review</span>" if needs_review else ""),
                    unsafe_allow_html=True
                )

            with right:
                st.markdown(confidence_bar(conf), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if r.get("reasoning"):
                    st.markdown(f'<div class="reasoning-box">💭 {r["reasoning"]}</div>',
                                unsafe_allow_html=True)
                if r.get("draft_response"):
                    st.markdown(f'<div class="draft-box">✉ {r["draft_response"]}</div>',
                                unsafe_allow_html=True)
                if error:
                    st.error(f"Triage error: {error}")

    # Download
    st.markdown("---")
    csv_out = results_to_csv(results)
    st.download_button(
        "⬇ Download triaged results CSV",
        data=csv_out,
        file_name="triaged_tickets.csv",
        mime="text/csv",
    )
