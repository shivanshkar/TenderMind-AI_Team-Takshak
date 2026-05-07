import os

import pandas as pd
import requests
import streamlit as st


API_BASE = os.getenv("TENDERMIND_API_URL", "http://localhost:8000").rstrip("/")


def color_decision(value):
    if value == "PASS":
        return "background-color: #ddf7e7; color: #116235; font-weight: 700"
    if value == "FAIL":
        return "background-color: #ffe1df; color: #9d2118; font-weight: 700"
    if value == "NEEDS_REVIEW":
        return "background-color: #fff2ca; color: #755200; font-weight: 700"
    return ""


st.set_page_config(page_title="TenderMind AI", layout="wide")

st.title("TenderMind AI")

status = st.empty()
try:
    health = requests.get(f"{API_BASE}/health", timeout=3)
    health.raise_for_status()
    status.success("Backend connected")
except requests.RequestException:
    status.error(f"Backend not reachable at {API_BASE}")

if "tender_id" not in st.session_state:
    st.session_state.tender_id = None
if "batch_id" not in st.session_state:
    st.session_state.batch_id = None
if "criteria" not in st.session_state:
    st.session_state.criteria = []
if "evaluation" not in st.session_state:
    st.session_state.evaluation = None

left, right = st.columns(2)

with left:
    st.subheader("Tender")
    tender_file = st.file_uploader("Upload tender PDF", type=["pdf"])
    if st.button("Upload Tender", disabled=tender_file is None):
        response = requests.post(
            f"{API_BASE}/upload-tender",
            files={"file": (tender_file.name, tender_file.getvalue(), "application/pdf")},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        st.session_state.tender_id = payload["id"]
        st.success(f"Tender uploaded: {payload['id']}")

with right:
    st.subheader("Bidders")
    bidder_zip = st.file_uploader("Upload bidder ZIP", type=["zip"])
    if st.button("Upload Bidders", disabled=bidder_zip is None):
        response = requests.post(
            f"{API_BASE}/upload-bidders",
            files={"file": (bidder_zip.name, bidder_zip.getvalue(), "application/zip")},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        st.session_state.batch_id = payload["id"]
        st.success(f"Bidder batch uploaded: {payload['id']}")

actions = st.columns([1, 1, 2])
with actions[0]:
    if st.button("Extract Criteria", disabled=st.session_state.tender_id is None):
        response = requests.post(
            f"{API_BASE}/extract-criteria",
            json={"tender_id": st.session_state.tender_id},
            timeout=120,
        )
        response.raise_for_status()
        st.session_state.criteria = response.json()["criteria"]

with actions[1]:
    if st.button(
        "Evaluate",
        disabled=st.session_state.tender_id is None or st.session_state.batch_id is None,
    ):
        response = requests.post(
            f"{API_BASE}/evaluate",
            json={
                "tender_id": st.session_state.tender_id,
                "bidder_batch_id": st.session_state.batch_id,
            },
            timeout=180,
        )
        response.raise_for_status()
        st.session_state.evaluation = response.json()

if st.session_state.criteria:
    st.subheader("Extracted Criteria")
    criteria_df = pd.DataFrame(
        [
            {
                "Criterion": item["name"],
                "Field": item["field_name"],
                "Rule": f"{item['operator']} {item.get('threshold')}",
                "Mandatory": item["mandatory"],
            }
            for item in st.session_state.criteria
        ]
    )
    st.dataframe(criteria_df, use_container_width=True, hide_index=True)

evaluation = st.session_state.evaluation
if evaluation:
    st.subheader("Evaluation Matrix")
    matrix_df = pd.DataFrame(evaluation["matrix"])
    st.dataframe(
        matrix_df.style.applymap(color_decision),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Scoring Summary")
    summary_df = pd.DataFrame.from_dict(evaluation["summary"], orient="index").reset_index()
    summary_df = summary_df.rename(columns={"index": "Bidder"})
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    flagged = [item for item in evaluation["evaluations"] if item["flagged"]]
    st.subheader("Flagged Cases")
    if flagged:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Bidder": item["bidder_name"],
                        "Criterion": item["criterion_name"],
                        "Decision": item["decision"],
                        "Confidence": item["confidence"],
                        "Source": item["source_document"],
                        "Reason": item["reasoning"],
                    }
                    for item in flagged
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No uncertain cases flagged.")

    st.link_button(
        "Open HTML Report",
        f"{API_BASE}/report?evaluation_id={evaluation['evaluation_id']}&format=html",
    )
