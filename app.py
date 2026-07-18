#!/usr/bin/env python3
"""Streamlit app for Utility Coordinator AI Assistant."""
from __future__ import annotations

import logging
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import streamlit as st

from config import get_settings
from database import get_session, init_db
from database.repositories import (
    AuditRepository,
    BillRepository,
    JobRepository,
    PaymentTaskRepository,
    TransactionRepository,
)
from models import BillStatus
from services import OllamaClient
from services.payment_service import prepare_mock_payment, submit_mock_payment
from workflows.ingestion_workflow import process_upload_zip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Utility Coordinator AI",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    init_db()
except Exception as exc:
    logger.warning("Database initialization note: %s", exc)

settings = get_settings()

if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None

with st.sidebar:
    st.title("⚙️ Configuration")
    st.info(
        "**Bill extraction and AI reasoning run locally through Ollama.**\n\n"
        "Bill documents are not sent to a cloud-hosted LLM.\n\n"
        "Mock provider interactions remain on localhost."
    )
    st.markdown("---")
    st.subheader("Ollama Status")
    client = OllamaClient()
    if client.is_available():
        st.success(f"✅ Connected to {settings.ollama_model}")
    else:
        st.error(f"❌ Cannot reach {settings.ollama_model}\n\nRun: `ollama serve`")
    st.markdown("---")
    st.caption(f"Min Confidence: {settings.min_confidence}")
    st.caption(f"High Amount Threshold: ${settings.high_amount_review_threshold:.2f}")

tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "📋 Bills", "💰 Payment Queue", "📊 Report"])

with tab1:
    st.header("Upload Utility Bills")
    st.write("Upload a ZIP file containing multiple utility bill PDFs.")
    uploaded_file = st.file_uploader("Choose a ZIP file", type="zip")

    if uploaded_file and st.button("🚀 Start Processing", use_container_width=True):
        with st.spinner("Processing bills locally with Gemma..."):
            session = get_session()
            try:
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    tmp_path = Path(tmp.name)
                result = process_upload_zip(tmp_path, session)
                tmp_path.unlink(missing_ok=True)

                if result["success"]:
                    st.success("✅ Processing complete")
                else:
                    st.error("❌ Processing failed")

                col1, col2, col3 = st.columns(3)
                col1.metric("Bills Created", result["bills_created"])
                col2.metric("Need Review", result["bills_needing_review"])
                col3.metric("Duplicates", result["duplicates_detected"])

                if result.get("errors"):
                    st.warning("Errors encountered:")
                    for error in result["errors"]:
                        st.write(f"• {error}")
                if result.get("job_id"):
                    st.info(f"Job ID: `{result['job_id']}`")
            except Exception as exc:
                st.error(f"❌ Error: {exc}")
                logger.error("Processing error: %s", exc, exc_info=True)
            finally:
                session.close()

with tab2:
    st.header("Extracted Bills")
    session = get_session()
    bill_repo = BillRepository(session)
    job_repo = JobRepository(session)

    jobs = job_repo.list_recent()
    selected_job = st.selectbox("Job", options=["All jobs"] + jobs, index=0)

    bills = bill_repo.get_by_job(selected_job) if selected_job != "All jobs" else bill_repo.list_all()
    session.close()

    if not bills:
        st.info("No bills yet. Upload a ZIP file to get started.")
    else:
        rows = []
        for bill in bills:
            rows.append(
                {
                    "bill_id": bill.bill_id,
                    "provider": bill.provider_name,
                    "utility_type": bill.utility_type.value,
                    "masked_account": bill.account_number_masked,
                    "service_address": bill.service_address,
                    "billing_period": f"{bill.billing_period_start} to {bill.billing_period_end}",
                    "amount_due": float(bill.amount_due),
                    "due_date": bill.due_date,
                    "payment_url": bill.verified_payment_url or "",
                    "confidence": bill.extraction_confidence,
                    "status": bill.status.value,
                    "review_reason": bill.review_reason or "",
                }
            )

        df = pd.DataFrame(rows)
        edited = st.data_editor(df, use_container_width=True, num_rows="fixed")

        if st.button("💾 Save Bill Edits"):
            session = get_session()
            bill_repo = BillRepository(session)
            for _, row in edited.iterrows():
                try:
                    amount = Decimal(str(row["amount_due"]))
                except InvalidOperation:
                    amount = Decimal("0.00")
                bill_repo.update(
                    row["bill_id"],
                    provider_name=row["provider"],
                    utility_type=row["utility_type"],
                    account_number_masked=row["masked_account"],
                    service_address=row["service_address"],
                    amount_due=amount,
                    due_date=row["due_date"],
                    verified_payment_url=row["payment_url"] or None,
                    status=row["status"],
                    review_reason=row["review_reason"] or None,
                    requires_review=row["status"] == BillStatus.NEEDS_REVIEW.value,
                )
            session.close()
            st.success("Bill edits saved.")

with tab3:
    st.header("Payment Task Queue")
    session = get_session()
    task_repo = PaymentTaskRepository(session)
    bill_repo = BillRepository(session)
    tasks = task_repo.list_all()
    session.close()

    if not tasks:
        st.info("No payment tasks yet. Process bills with status `ready` first.")
    else:
        for task in tasks:
            session = get_session()
            bill_repo = BillRepository(session)
            bill = bill_repo.get(task.bill_id)
            session.close()
            if not bill:
                continue

            with st.expander(f"Priority {task.priority} | {bill.provider_name} | ${bill.amount_due:.2f}"):
                st.write(f"Status: **{task.status.value}**")
                st.write(f"Due date: {bill.due_date}")
                st.write(f"Payment URL: {bill.verified_payment_url}")

                col1, col2, col3 = st.columns(3)
                if col1.button("Prepare mock payment", key=f"prep_{task.task_id}"):
                    session = get_session()
                    try:
                        approval_payload = prepare_mock_payment(session, task.task_id)
                        st.session_state.pending_approval = {
                            "task_id": task.task_id,
                            **approval_payload,
                        }
                        st.success("Reached review page. Approval required.")
                    except Exception as exc:
                        st.error(str(exc))
                    finally:
                        session.close()

                if col2.button("Skip bill", key=f"skip_{task.task_id}"):
                    session = get_session()
                    task_repo = PaymentTaskRepository(session)
                    task_repo.update(task.task_id, status="cancelled")
                    session.close()
                    st.warning("Task skipped.")

    pending = st.session_state.pending_approval
    if pending:
        st.markdown("---")
        st.subheader("Human Approval Gate")
        st.write(f"**Provider:** {pending['provider']}")
        st.write(f"**Masked account number:** {pending['account_number_masked']}")
        st.write(f"**Amount:** ${pending['amount']}")
        st.write(f"**Payment method placeholder:** {pending['payment_method']}")
        st.write(f"**Scheduled date:** {pending['scheduled_date']}")

        approve_col, cancel_col = st.columns(2)
        if approve_col.button("Approve mock payment"):
            session = get_session()
            try:
                result = submit_mock_payment(session, pending["task_id"], approved=True)
                if result.get("success"):
                    st.success(f"Payment verified. Confirmation: {result['confirmation_number']}")
                else:
                    st.error(result.get("error", "Payment failed"))
                st.session_state.pending_approval = None
            except Exception as exc:
                st.error(str(exc))
            finally:
                session.close()

        if cancel_col.button("Cancel"):
            session = get_session()
            try:
                submit_mock_payment(session, pending["task_id"], approved=False)
                st.session_state.pending_approval = None
                st.info("Payment cancelled.")
            finally:
                session.close()

with tab4:
    st.header("Audit Report")
    session = get_session()
    bill_repo = BillRepository(session)
    txn_repo = TransactionRepository(session)
    audit_repo = AuditRepository(session)

    bills = bill_repo.list_all()
    transactions = txn_repo.list_all()
    events = audit_repo.list_recent(limit=100)
    session.close()

    total_due = sum(float(b.amount_due) for b in bills)
    paid = [b for b in bills if b.status == BillStatus.PAID]
    pending = [b for b in bills if b.status in {BillStatus.READY, BillStatus.AWAITING_APPROVAL}]
    failed = [b for b in bills if b.status == BillStatus.FAILED]
    duplicates = [b for b in bills if b.status == BillStatus.DUPLICATE]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bills", len(bills))
    c2.metric("Total Amount Due", f"${total_due:.2f}")
    c3.metric("Successfully Paid", len(paid))
    c4.metric("Pending", len(pending))

    st.write(f"Failed bills: **{len(failed)}** | Duplicate bills: **{len(duplicates)}**")

    if transactions:
        st.subheader("Confirmation Numbers")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "provider": txn.provider_name,
                        "amount": float(txn.amount),
                        "confirmation_number": txn.confirmation_number,
                        "screenshot_path": txn.screenshot_path,
                        "status": txn.verification_status,
                    }
                    for txn in transactions
                ]
            ),
            use_container_width=True,
        )

    st.subheader("Audit Event Timeline")
    if events:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "timestamp": event.timestamp,
                        "event_type": event.event_type.value,
                        "actor": event.actor,
                        "job_id": event.job_id,
                        "bill_id": event.bill_id or "",
                        "task_id": event.task_id or "",
                    }
                    for event in events
                ]
            ),
            use_container_width=True,
        )
    else:
        st.info("No audit events yet.")

st.markdown("---")
st.caption(f"Utility Coordinator v0.2.0 | Local Gemma ({settings.ollama_model}) | SQLite")
