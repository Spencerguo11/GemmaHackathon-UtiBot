#!/usr/bin/env python3
"""Streamlit app for Utility Coordinator AI Assistant."""
import streamlit as st
import logging
from datetime import datetime
from pathlib import Path
import tempfile

from config import get_settings, PROJECT_ROOT
from database import init_db, get_session
from database.repositories import BillRepository, JobRepository, AuditRepository
from services import OllamaClient
from workflows.ingestion_workflow import process_upload_zip

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Streamlit
st.set_page_config(
    page_title="Utility Coordinator AI",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database
try:
    init_db()
except Exception as e:
    logger.warning(f"Database already initialized: {e}")

settings = get_settings()

# Sidebar
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
    st.subheader("Settings")
    st.caption(f"Min Confidence: {settings.min_confidence}")
    st.caption(f"High Amount Threshold: ${settings.high_amount_review_threshold:.2f}")

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "📋 Bills", "💰 Payment Queue", "📊 Report"])

# ===== TAB 1: UPLOAD =====
with tab1:
    st.header("Upload Utility Bills")
    
    st.write("Upload a ZIP file containing multiple utility bill PDFs.")
    
    uploaded_file = st.file_uploader(
        "Choose a ZIP file",
        type="zip",
        help="ZIP should contain PDF files only"
    )
    
    if uploaded_file:
        st.write(f"📦 Selected: **{uploaded_file.name}**")
        
        if st.button("🚀 Start Processing", use_container_width=True):
            with st.spinner("Processing bills..."):
                try:
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        tmp_path = Path(tmp.name)
                    
                    # Process
                    session = get_session()
                    result = process_upload_zip(tmp_path, session)
                    session.close()
                    
                    # Display results
                    st.success(f"✅ Processing Complete!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Bills Created", result["bills_created"])
                    with col2:
                        st.metric("Need Review", result["bills_needing_review"])
                    with col3:
                        st.metric("Duplicates", result["duplicates_detected"])
                    
                    if result.get("errors"):
                        st.warning("⚠️ Errors encountered:")
                        for error in result["errors"]:
                            st.write(f"• {error}")
                    
                    st.info(f"Job ID: `{result['job_id']}`")
                    
                    # Cleanup
                    tmp_path.unlink()
                
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    logger.error(f"Processing error: {e}", exc_info=True)

# ===== TAB 2: BILLS =====
with tab2:
    st.header("Extracted Bills")
    
    # Job selector
    session = get_session()
    job_repo = JobRepository(session)
    bill_repo = BillRepository(session)
    
    # Get recent jobs
    jobs = session.query(session.get_bind().execute_compiled(
        "SELECT DISTINCT job_id FROM bills ORDER BY created_at DESC LIMIT 10"
    )).all()
    
    if not jobs:
        st.info("No bills yet. Upload a ZIP file to get started.")
    else:
        # Simple job selector - using first job for now
        session.close()
        session = get_session()
        bill_repo = BillRepository(session)
        
        # Get all bills
        bills = session.query(session.get_bind().execute_compiled(
            "SELECT * FROM bills ORDER BY due_date ASC"
        )).all()
        
        if bills:
            st.write(f"Found **{len(bills)}** bills")
            
            # Display as table
            bill_data = []
            for bill in bills:
                bill_data.append({
                    "Provider": bill.provider_name,
                    "Type": bill.utility_type,
                    "Account": bill.account_number_masked,
                    "Due Date": bill.due_date,
                    "Amount": f"${float(bill.amount_due):.2f}",
                    "Status": bill.status,
                })
            
            st.dataframe(bill_data, use_container_width=True)
        else:
            st.info("No bills found.")
    
    session.close()

# ===== TAB 3: PAYMENT QUEUE =====
with tab3:
    st.header("Payment Task Queue")
    st.info("💰 Payment automation features coming in Phase 5+")
    st.write("This tab will show:")
    st.write("• Prioritized bills ready for payment")
    st.write("• Human approval gate")
    st.write("• Mock provider payment flow")

# ===== TAB 4: REPORT =====
with tab4:
    st.header("Audit Report")
    st.info("📊 Audit reporting features coming in Phase 8+")
    st.write("This tab will show:")
    st.write("• Summary statistics")
    st.write("• Audit event timeline")
    st.write("• Payment confirmations")
    st.write("• Screenshot gallery")

# Footer
st.markdown("---")
st.caption(
    f"Utility Coordinator v0.1.0 | Gemma 4 ({settings.ollama_model}) | SQLite Database"
)
