import streamlit as st
import xml.etree.ElementTree as ET
import sqlite3
import pandas as pd
from datetime import datetime, timezone

st.set_page_config(
    page_title="B2B Integration & Incident Triage Console",
    page_icon="🛠️",
    layout="wide"
)

@st.cache_resource
def init_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE b2b_transactions (
            order_id TEXT PRIMARY KEY,
            partner_id TEXT,
            partner_name TEXT,
            feed_type TEXT,
            status TEXT,
            error_code TEXT,
            timestamp TEXT
        )
    """)
    sample_data = [
        ("ORD-1001", "PART-88", "Acme Retail Corp", "XML Product Feed", "PROCESSED", "200 OK", "2026-11-19 08:15:00"),
        ("ORD-1002", "PART-92", "Global Mart LLC", "AS2 Purchase Order", "FAILED", "AS2-401 (Expired Cert)", "2026-11-19 08:42:10"),
        ("ORD-1003", "PART-88", "Acme Retail Corp", "Catalog Sync (XML)", "FAILED", "XML-ERR (Missing SKU)", "2026-11-19 09:05:33"),
        ("ORD-1004", "PART-45", "NorthStar Supply", "Web Service REST", "PENDING_RETRY", "HTTP-504 (Timeout)", "2026-11-19 09:30:12"),
        ("ORD-1005", "PART-12", "Apex Distributors", "AS2 Invoice", "FAILED", "MDN-MISSING", "2026-11-19 10:11:45"),
    ]
    cursor.executemany("INSERT INTO b2b_transactions VALUES (?, ?, ?, ?, ?, ?, ?)", sample_data)
    conn.commit()
    return conn

conn = init_db()

st.title("🛠️ B2B Integration & Incident Triage Console")
st.markdown(
    "**Tier-1 Technical Support Toolkit** | Validate XML Product/Order Feeds, Diagnose AS2 & Web Service Errors, "
    "Query Transaction Logs (SQL), and Generate SLA-Compliant Ticket Notes."
)
st.divider()

tab1, tab2, tab3 = st.tabs([
    "1️⃣ XML Feed Validator",
    "2️⃣ AS2 & Web Service Diagnostics",
    "3️⃣ SQL Order Lookup & Ticket Generator"
])

with tab1:
    st.subheader("XML Payload & Schema Validator")
    st.write("Paste an incoming B2B XML payload (e.g., Catalog Feed or Purchase Order) to verify well-formedness and mandatory nodes.")

    sample_valid_xml = (
        "<Order>\n"
        "    <OrderID>ORD-1006</OrderID>\n"
        "    <CustomerID>PART-88</CustomerID>\n"
        "    <Timestamp>2026-11-19T11:00:00Z</Timestamp>\n"
        "    <Item>\n"
        "        <SKU>PROD-9921</SKU>\n"
        "        <Quantity>25</Quantity>\n"
        "    </Item>\n"
        "</Order>"
    )

    sample_broken_xml = (
        "<Order>\n"
        "    <OrderID>ORD-1007</OrderID>\n"
        "    <Timestamp>2026-11-19T11:05:00Z</Timestamp>\n"
        "    <Item>\n"
        "        <SKU>PROD-4410</SKU>\n"
        "        <Quantity>10\n"
        "    </Item>\n"
        "</Order>"
    )

    col_btn1, col_btn2, _ = st.columns(3)
    if col_btn1.button("Load Valid XML Sample"):
        st.session_state["xml_input"] = sample_valid_xml
    if col_btn2.button("Load Broken XML Sample"):
        st.session_state["xml_input"] = sample_broken_xml

    xml_payload = st.text_area(
        "XML Payload Input:",
        value=st.session_state.get("xml_input", sample_valid_xml),
        height=220
    )

    if st.button("🔍 Validate XML Payload", type="primary"):
        if not xml_payload.strip():
            st.warning("Please enter an XML payload to validate.")
        else:
            try:
                root = ET.fromstring(xml_payload)
                st.success(f"✅ **Syntax Check Passed:** XML is well-formed (Root element: `<{root.tag}>`).")

                required_tags = ["OrderID", "CustomerID", "SKU"]
                missing_tags = []
                for tag in required_tags:
                    element = root.find(f".//{tag}")
                    if element is None or not (element.text and element.text.strip()):
                        missing_tags.append(tag)

                if missing_tags:
                    st.error(f"❌ **Schema Validation Failed:** Missing or empty mandatory nodes: `{', '.join(missing_tags)}`")
                    st.info("**Tier-1 Action:** Reject feed, notify partner with missing field details, and log under SLA.")
                else:
                    st.success("✅ **Schema Check Passed:** All mandatory nodes (`OrderID`, `CustomerID`, `SKU`) are present and populated.")
            except ET.ParseError as e:
                st.error(f"❌ **XML ParseError (Malformed Syntax):** {e}")
                st.info("**Tier-1 Action:** Check for unclosed tags or invalid characters (e.g., unescaped `&`) and request corrected file from partner.")

with tab2:
    st.subheader("AS2 & Web Service Error Runbook")
    st.write("Select a reported integration error code to view root cause analysis, troubleshooting steps, and escalation rules.")

    error_kb = {
        "AS2-401: Unauthorized / Expired Certificate": {
            "severity": "High (SLA: 2 Hours)",
            "root_cause": "The trading partner's public encryption/signing certificate has expired or does not match the AS2 station ID.",
            "steps": [
                "1. Verify AS2 Station ID and Partner ID in the integration gateway.",
                "2. Check certificate expiration date in the Partner Profile.",
                "3. Request the updated public certificate (.cer/.pem) from the partner's technical contact.",
                "4. Upload new certificate and trigger a test ping."
            ],
            "escalate": "No (Tier-1 can resolve once partner provides valid certificate; escalate to Tier-2 only if gateway reload fails)."
        },
        "MDN-MISSING: Synchronous/Asynchronous MDN Not Received": {
            "severity": "Medium (SLA: 4 Hours)",
            "root_cause": "Payload was transmitted over HTTP/S, but the partner server failed to return a Message Disposition Notification (MDN) receipt.",
            "steps": [
                "1. Check outbound transmission logs to confirm HTTP 200 acknowledgement.",
                "2. Verify if partner expects Synchronous or Asynchronous MDN.",
                "3. Confirm firewall/allowlist rules allow inbound MDN callbacks on port 443.",
                "4. Avoid duplicate resends until partner confirms whether the original message was ingested."
            ],
            "escalate": "Yes — Escalate to Tier-2 Network/EDI Team if MDN timeout persists after 2 retry cycles."
        },
        "HTTP-504: Web Service Gateway Timeout": {
            "severity": "High (SLA: 2 Hours)",
            "root_cause": "Target API endpoint (REST/SOAP) took too long to process a large product catalog batch.",
            "steps": [
                "1. Check payload size (batches over 10MB often trigger gateway timeouts).",
                "2. Test endpoint health using cURL or Postman.",
                "3. Split large catalog XML/JSON feeds into smaller chunks and re-queue.",
                "4. Monitor response codes in server logs."
            ],
            "escalate": "Yes — Escalate to Tier-2 Application Engineering if endpoint latency affects normal-sized payloads."
        },
        "HTTP-400: Bad Request / Invalid Data Mapping": {
            "severity": "Low/Medium (SLA: 8 Hours)",
            "root_cause": "Incoming feed contains invalid data types (e.g., text in a numeric price field) or unsupported currency/rate codes.",
            "steps": [
                "1. Inspect raw request body in API logs.",
                "2. Compare payload fields against the XSD/JSON schema specification.",
                "3. Identify exact line/field causing rejection.",
                "4. Send formatted error report to partner so they can fix source mapping."
            ],
            "escalate": "No (Resolved at Tier-1 via partner communication and data validation)."
        }
    }

    selected_error = st.selectbox("Select Integration Incident Type:", list(error_kb.keys()))
    details = error_kb[selected_error]

    col_a, col_b = st.columns(2)
    col_a.metric("SLA Priority", details["severity"])
    col_b.info(f"**Escalation Policy:** {details['escalate']}")

    st.markdown(f"**Probable Root Cause:** {details['root_cause']}")
    st.markdown("**Standard Operating Procedure (Troubleshooting Steps):**")
    for step in details["steps"]:
        st.write(step)

with tab3:
    st.subheader("Transaction Database Lookup (SQL) & Ticket Documentation")

    col_search1, col_search2 = st.columns(2)
    search_term = col_search1.text_input("Search by Order ID or Partner ID (leave blank to view all):", placeholder="e.g., ORD-1002 or PART-88")
    status_filter = col_search2.selectbox("Filter by Status:", ["ALL", "FAILED", "PENDING_RETRY", "PROCESSED"])

    query = "SELECT * FROM b2b_transactions WHERE 1=1"
    params = []

    if search_term.strip():
        query += " AND (order_id LIKE ? OR partner_id LIKE ? OR partner_name LIKE ?)"
        like_val = f"%{search_term.strip()}%"
        params.extend([like_val, like_val, like_val])

    if status_filter != "ALL":
        query += " AND status = ?"
        params.append(status_filter)

    st.code(f"-- Executed SQL Query:\n{query}", language="sql")

    df = pd.read_sql_query(query, conn, params=params)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### 📝 Auto-Generate Ticket Resolution Note")
    col_t1, col_t2, col_t3 = st.columns(3)
    ticket_order = col_t1.selectbox("Select Order ID:", df["order_id"].tolist() if not df.empty else ["ORD-1002"])
    action_taken = col_t2.selectbox("Action Taken:", [
        "Validated XML payload & notified partner of missing fields",
        "Verified AS2 certificate status & requested renewal from partner",
        "Re-queued failed batch after confirming endpoint availability",
        "Escalated persistent timeout to Tier-2 Engineering with logs"
    ])
    ticket_status = col_t3.selectbox("New Ticket Status:", ["Pending Partner Response", "Escalated to Tier-2", "Resolved - Verified"])

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    note_text = (
        "--- TIER-1 SUPPORT INCIDENT NOTE ---\n"
        f"Timestamp (UTC): {ts}\n"
        f"Order / Feed Reference: {ticket_order}\n"
        "Investigation Summary: Queried b2b_transactions table and inspected incoming payload/gateway logs.\n"
        f"Action Taken: {action_taken}.\n"
        f"Current Status: {ticket_status}\n"
        "SLA Compliance: Investigated within Tier-1 response window."
    )

    st.text_area("Copy & Paste into Service Desk (Zendesk / Jira):", value=note_text, height=160)
