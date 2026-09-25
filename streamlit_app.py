"""Run with: python -m streamlit run streamlit_app.py"""

import hashlib
import os
import re

import requests
import streamlit as st

LOCAL_API_URL = os.environ.get("FAQ_API_URL", "http://127.0.0.1:8767").rstrip("/")
CLOUD_API_URL = os.environ.get("FAQ_CLOUD_API_URL", "http://127.0.0.1:8768").rstrip("/")
st.set_page_config(
    page_title="Qdrant FAQ workspace", page_icon=":material/description:", layout="wide"
)


def change_target():
    # Never carry previews, approval, upload widgets or conversation across environments.
    for key in list(st.session_state):
        if key != "cloud_target":
            del st.session_state[key]


with st.sidebar:
    cloud_target = st.toggle("Qdrant Cloud", key="cloud_target", on_change=change_target)
    st.caption("Destination: Qdrant Cloud" if cloud_target else "Destination: Local Qdrant")
API_URL = CLOUD_API_URL if cloud_target else LOCAL_API_URL
COLLECTION_KEY = "cloud_collection" if cloud_target else "collection"
st.session_state.setdefault("preview", None)
st.session_state.setdefault("history", [])
st.session_state.setdefault("scope", None)


def api(method, path, **kwargs):
    try:
        response = requests.request(
            method, API_URL + path, timeout=kwargs.pop("timeout", 90), **kwargs
        )
    except requests.RequestException:
        st.error("The API could not be reached or timed out. Check that it is running, then retry.")
        st.stop()
    if not response.ok:
        try:
            detail = response.json().get("detail", "Request failed")
        except ValueError:
            detail = "Request failed"
        if isinstance(detail, dict):
            detail = (
                f"{detail.get('message', 'Request failed')} Request: {detail.get('request_id', '')}"
            )
        elif not isinstance(detail, str):
            if path == "/collections" and response.status_code == 422:
                detail = (
                    "Collection name: use 3-48 characters, start with a lowercase letter, "
                    "and use only lowercase letters, digits, underscores or hyphens. "
                    "Example: pulse360_faq"
                )
            else:
                detail = "Invalid request. Check the file or question."
        st.error(f"HTTP {response.status_code}: {detail}")
        st.stop()
    return response.json()


def evidence(items):
    for index, hit in enumerate(items, 1):
        with st.expander(f"Source {index} | {hit.get('filename') or hit.get('title', 'Document')}"):
            with st.container(horizontal=True):
                st.metric("Vector score", f"{hit['vector_score']:.4f}")
                if hit.get("page"):
                    st.metric("Page", hit["page"])
            if hit.get("text"):
                st.text(hit["text"])
            st.caption(f"Chunk: {hit['chunk_id']}")


st.title("Qdrant FAQ workspace")
collections = api("GET", "/collections", timeout=15)
names = [c["id"] for c in collections]
pending = st.session_state.pop("select_next", None)
if pending in names:
    st.session_state[COLLECTION_KEY] = pending
if st.session_state.get(COLLECTION_KEY) not in names:
    st.session_state.pop(COLLECTION_KEY, None)

with st.sidebar:
    st.header("Collections")
    chosen = st.selectbox(
        "Active collection", names, index=0 if names else None, key=COLLECTION_KEY
    )
    if st.button("", icon=":material/refresh:", help="Refresh collections", key="refresh"):
        st.rerun()
    with st.form("create_collection"):
        name = st.text_input(
            "New collection name",
            placeholder="pulse360_faq",
            max_chars=48,
        )
        st.caption(
            "**Naming requirements**\n\n"
            "- 3-48 characters\n"
            "- Start with a lowercase letter\n"
            "- Use lowercase letters, digits, underscores (`_`) or hyphens (`-`)\n"
            "- No spaces or uppercase letters\n\n"
            "Example: `pulse360_faq_v2`"
        )
        if st.form_submit_button("Create collection", icon=":material/add:"):
            if not re.fullmatch(r"[a-z][a-z0-9_-]{2,47}", name.strip()):
                st.error(
                    "Collection name: use 3-48 characters, start with a lowercase letter, "
                    "and use only lowercase letters, digits, underscores or hyphens. "
                    "Example: pulse360_faq"
                )
                st.stop()
            result = api("POST", "/collections", json={"name": name.strip()})
            st.session_state.select_next = result["id"]
            st.session_state.notice = "Collection created."
            st.rerun()
    st.divider()
    st.link_button("API docs", API_URL + "/docs", icon=":material/api:")

if notice := st.session_state.pop("notice", None):
    st.success(notice)
if not chosen:
    st.info("No collections yet.")
    st.stop()
collection = next(c for c in collections if c["id"] == chosen)
if not collection["compatible"]:
    st.error("This collection uses a different embedding configuration.")
    st.stop()
if st.session_state.get("active_collection") != chosen:
    st.session_state.preview = None
    st.session_state.active_collection = chosen

docs = api("GET", f"/collections/{chosen}/documents", timeout=15)
with st.container(horizontal=True):
    st.metric("Documents", len(docs))
    st.metric("Stored chunks", sum(d["chunks"] for d in docs))
    st.metric("Vector dimensions", collection["dimensions"])
st.caption(f"{collection['physical_name']} | {collection['embedding_model']}")

documents_tab, questions_tab = st.tabs(["Documents", "Questions"])
with documents_tab:
    st.subheader("Upload document")
    upload = st.file_uploader("Document", type=["pdf", "txt", "md"], key=f"upload_{chosen}")
    data = upload.getvalue() if upload else None
    signature = (chosen, upload.name, hashlib.sha256(data).hexdigest()) if upload else None
    if st.session_state.get("upload_signature") != signature:
        st.session_state.preview = None
        st.session_state.upload_signature = signature
    if st.button(
        "Preview chunks", icon=":material/preview:", disabled=upload is None, key="preview_button"
    ):
        if len(data) > 10 * 1024 * 1024:
            st.error("Maximum upload size is 10 MB.")
        else:
            with st.spinner("Extracting text..."):
                st.session_state.preview = api(
                    "POST",
                    f"/collections/{chosen}/uploads/preview",
                    files={"file": (upload.name, data)},
                    timeout=60,
                )
    preview = st.session_state.preview
    if preview:
        st.subheader("Chunk preview")
        st.caption(
            f"{preview['chunk_count']} chunks | {preview['dimensions']} dimensions per vector | Not yet embedded"
        )
        chunks = preview["chunks"]
        chunk_index = st.selectbox(
            "Chunk",
            range(len(chunks)),
            format_func=lambda i: f"{i + 1} of {len(chunks)}",
            key=preview["preview_id"],
        )
        chunk = chunks[chunk_index]
        st.text(chunk["text"])
        st.caption(
            f"Page: {chunk['metadata'].get('page') or '-'} | Characters: {len(chunk['text'])}"
        )
        if preview["already_stored"]:
            st.info("This document is already stored in this collection.")
        else:
            approved = st.checkbox(
                "I approve sending this document to Hugging Face for embeddings and answer generation.",
                key="approval_" + preview["preview_id"],
            )
            if st.button(
                "Embed and store",
                icon=":material/cloud_upload:",
                type="primary",
                disabled=not approved,
                key="store_button",
            ):
                with st.spinner("Embedding and storing..."):
                    result = api(
                        "POST",
                        f"/collections/{chosen}/documents",
                        timeout=600,
                        json={"preview_id": preview["preview_id"], "approved": approved},
                    )
                st.session_state.preview = None
                st.session_state.notice = f"Document stored: {result['chunks']} chunks."
                st.rerun()
    st.divider()
    st.subheader("Stored documents")
    if docs:
        for document in docs:
            st.text(f"{document['filename']} | {document['chunks']} chunks")
            st.caption(document["id"])
    else:
        st.info("No stored documents in this collection.")

with questions_tab:
    st.subheader("Questions")
    mode = (
        st.segmented_control("Response", ["Answer", "Search"], default="Answer", key="mode")
        or "Answer"
    )
    doc_names = {d["id"]: d["filename"] for d in docs}
    document_id = st.selectbox(
        "Document scope",
        [None, *doc_names],
        format_func=lambda v: doc_names[v] if v else "All documents",
        key="doc_" + chosen,
    )
    scope = (chosen, document_id, mode)
    if st.session_state.scope != scope:
        st.session_state.history = []
        st.session_state.scope = scope
    if st.button("", icon=":material/delete_sweep:", help="Clear question history", key="clear"):
        st.session_state.history = []
    for item in st.session_state.history:
        with st.chat_message("user"):
            st.text(item["question"])
        with st.chat_message("assistant"):
            st.text(item["answer"])
            evidence(item["sources"])
            st.caption(f"Request: {item['request_id']}")
    question = st.chat_input("Ask about the selected documents", max_chars=800, disabled=not docs)
    if question:
        body = {"question": question, "collection_id": chosen}
        if document_id:
            body["document_id"] = document_id
        with st.spinner("Searching..." if mode == "Search" else "Preparing answer..."):
            result = api("POST", "/search" if mode == "Search" else "/ask", json=body)
        sources = result.get("matches", result.get("sources", []))
        st.session_state.history.append(
            {
                "question": question,
                "answer": result.get("answer", f"{len(sources)} matching chunks."),
                "sources": sources,
                "request_id": result["request_id"],
            }
        )
        st.session_state.history = st.session_state.history[-20:]
        st.rerun()
