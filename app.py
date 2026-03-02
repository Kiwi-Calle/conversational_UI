import json
import streamlit as st
from google.cloud import geminidataanalytics
from google.api_core import retry
from google.api_core import exceptions as gexc
from google.protobuf.json_format import MessageToDict

# ----------------------------
# 1) Page setup + styling
# ----------------------------
st.set_page_config(page_title="Conversational Agent", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #36454F; }
    p, h1, h2, h3, h4, h5, h6, span, div { color: #FAFAFA !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# 2) Helpers
# ----------------------------
def _extract_text(obj) -> str:
    """Best-effort extractor for different SDK text shapes."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj

    t = getattr(obj, "text", None)
    if isinstance(t, str):
        return t

    if t is not None:
        t2 = getattr(t, "text", None)
        if isinstance(t2, str):
            return t2

    return ""


def _to_dict(proto_obj) -> dict:
    """Convert protobuf message to a JSON-serializable dict (best effort)."""
    try:
        pb = getattr(proto_obj, "_pb", proto_obj)
        return MessageToDict(pb, preserving_proto_field_name=True)
    except Exception:
        return {"repr": repr(proto_obj)}


def parse_agent_raw(raw_messages: list[dict]) -> dict:
    """
    Pull useful parts out of the agent's raw messages.
    - THOUGHT blocks: shown openly
    - FINAL_RESPONSE blocks: shown openly
    - SQL / job / schema / datasources: shown in expanders
    """
    out = {
        "final_text_blocks": [],
        "thought_blocks": [],
        "generated_sql": None,
        "bq_job": None,
        "result_rows": [],
        "result_name": None,
        "result_schema": None,
        "datasources": [],
    }

    for m in raw_messages or []:
        sm = (m.get("system_message") or {})
        text = (sm.get("text") or {})
        data = (sm.get("data") or {})

        # Text blocks (THOUGHT / FINAL_RESPONSE)
        if text:
            text_type = text.get("text_type")
            parts = text.get("parts") or []
            block = "\n".join([p for p in parts if isinstance(p, str)]).strip()
            if block:
                if text_type == "FINAL_RESPONSE":
                    out["final_text_blocks"].append(block)
                elif text_type == "THOUGHT":
                    out["thought_blocks"].append(block)

        # Datasources
        query = (data.get("query") or {})
        datasources = query.get("datasources")
        if isinstance(datasources, list) and datasources:
            out["datasources"].extend(datasources)

        # SQL
        if "generated_sql" in data and isinstance(data["generated_sql"], str):
            out["generated_sql"] = data["generated_sql"]

        # BigQuery job
        if "big_query_job" in data and isinstance(data["big_query_job"], dict):
            out["bq_job"] = data["big_query_job"]

        # Result set
        result = data.get("result")
        if isinstance(result, dict):
            rows = result.get("data")
            if isinstance(rows, list):
                out["result_rows"] = rows
            out["result_name"] = result.get("name") or out["result_name"]
            out["result_schema"] = result.get("schema") or out["result_schema"]

    return out


def render_agent_output(parsed: dict, raw_messages: list[dict] | None = None):
    """
    Show:
      - ALL agent THOUGHT blocks (visible)
      - ALL FINAL_RESPONSE blocks (visible)
    Clickable expanders for:
      - Result table (optional)
      - Generated SQL
      - Result schema
      - BigQuery job details
      - Datasources used
      - Full raw JSON download
    """

    # --- Visible: Thoughts ---
    thought_blocks = parsed.get("thought_blocks") or []
    if thought_blocks:
        st.subheader("Agent thoughts")
        for i, tb in enumerate(thought_blocks, start=1):
            st.markdown(f"**Thought {i}**\n\n{tb}")
    else:
        st.subheader("Agent thoughts")
        st.markdown("_No THOUGHT messages returned._")

    st.divider()

    # --- Visible: Final response (Summary/Insights/Follow-ups) ---
    final_blocks = parsed.get("final_text_blocks") or []
    if final_blocks:
        st.subheader("Answer")
        st.markdown("\n\n".join(final_blocks))
    else:
        st.subheader("Answer")
        st.markdown("_No FINAL_RESPONSE text found._")

    # --- Clickable: Result table ---
    rows = parsed.get("result_rows") or []
    if rows:
        title = "Result table"
        if parsed.get("result_name"):
            title = f"Result table ({parsed['result_name']})"
        with st.expander(title, expanded=False):
            st.dataframe(rows, use_container_width=True)

    # --- Clickable: SQL ---
    sql = parsed.get("generated_sql")
    if sql:
        with st.expander("Generated SQL", expanded=False):
            st.code(sql, language="sql")

    # --- Clickable: Schema ---
    schema = parsed.get("result_schema")
    if schema:
        with st.expander("Result schema", expanded=False):
            st.json(schema)

    # --- Clickable: Job details ---
    job = parsed.get("bq_job")
    if job:
        with st.expander("BigQuery job details", expanded=False):
            st.json(job)

    # --- Clickable: Datasources ---
    datasources = parsed.get("datasources") or []
    if datasources:
        with st.expander("Datasources used", expanded=False):
            st.json(datasources)

    # --- Clickable: Raw JSON + Download ---
    if raw_messages:
        with st.expander("Raw agent output (JSON)", expanded=False):
            st.json(raw_messages[:50])  # cap to keep UI fast

            raw_json_str = json.dumps(raw_messages, indent=2, ensure_ascii=False)
            st.download_button(
                "Download full raw response (JSON)",
                data=raw_json_str,
                file_name="agent_response.json",
                mime="application/json",
                use_container_width=True,
            )


@st.cache_resource
def get_data_chat_client() -> geminidataanalytics.DataChatServiceClient:
    return geminidataanalytics.DataChatServiceClient()


# ----------------------------
# 3) Non-streaming Data Agent call
# ----------------------------
def ask_data_agent(user_prompt: str) -> dict:
    data_chat_client = get_data_chat_client()

    project_id = "ctrl-digital-ga4"
    location = "global"
    raw_agent_id = "agent_ae90c1a1-04c1-4cd8-810a-736137d572c4"
    clean_agent_id = raw_agent_id.split("/")[-1]

    agent_path = data_chat_client.data_agent_path(project_id, location, clean_agent_id)

    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id}/locations/{location}",
        messages=[
            geminidataanalytics.Message(
                user_message=geminidataanalytics.UserMessage(text=user_prompt)
            )
        ],
        data_agent_context=geminidataanalytics.DataAgentContext(data_agent=agent_path),
    )

    chat_retry = retry.Retry(
        predicate=retry.if_exception_type(
            gexc.ServiceUnavailable,
            gexc.DeadlineExceeded,
            gexc.ResourceExhausted,
        ),
        initial=1.0,
        maximum=20.0,
        multiplier=2.0,
        deadline=120.0,
    )

    try:
        raw_messages: list[dict] = []

        responses = data_chat_client.chat(
            request=request,
            timeout=300.0,
            retry=chat_retry,
        )

        # Collect everything
        for resp in responses:
            for msg in getattr(resp, "messages", []):
                raw_messages.append(_to_dict(msg))

        # Parse into a clean structure
        parsed = parse_agent_raw(raw_messages)

        return {"ok": True, "parsed": parsed, "raw": raw_messages}

    except Exception as e:
        return {"ok": False, "error": f"Oops! I couldn't reach the Data Agent. Error: {e}"}


# ----------------------------
# 4) Multi-chat session state
# ----------------------------
if "chats" not in st.session_state:
    st.session_state.chats = {"Conversation 1": []}

if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Conversation 1"


# ----------------------------
# 5) Sidebar (chat history)
# ----------------------------
with st.sidebar:
    st.title("💬 Chat History")

    if st.button("➕ New Conversation", use_container_width=True):
        new_chat_name = f"Conversation {len(st.session_state.chats) + 1}"
        st.session_state.chats[new_chat_name] = []
        st.session_state.current_chat = new_chat_name
        st.rerun()

    st.divider()

    for chat_name in st.session_state.chats.keys():
        is_active = "✅ " if chat_name == st.session_state.current_chat else ""
        if st.button(f"{is_active}{chat_name}", use_container_width=True):
            st.session_state.current_chat = chat_name
            st.rerun()


# ----------------------------
# 6) Main Chat UI
# ----------------------------
st.title(f"📊 {st.session_state.current_chat}")

current_messages = st.session_state.chats[st.session_state.current_chat]
for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ----------------------------
# 7) User Input Handling (NON-STREAMING)
# ----------------------------
if prompt := st.chat_input("Ask about your GA4 data..."):
    # Save user message
    st.session_state.chats[st.session_state.current_chat].append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant response (render cleaned output in UI)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data in BigQuery..."):
            result = ask_data_agent(prompt)

        if not result.get("ok"):
            err = result.get("error", "Unknown error.")
            st.markdown(err)
            st.session_state.chats[st.session_state.current_chat].append(
                {"role": "assistant", "content": err}
            )
        else:
            parsed = result["parsed"]
            raw_messages = result["raw"]

            # Render nicely: thoughts + answer visible, rest clickable
            render_agent_output(parsed, raw_messages=raw_messages)

            # Save a compact summary to chat history (avoid storing huge JSON)
            saved_text = ""
            if parsed.get("thought_blocks"):
                saved_text += "Agent thoughts:\n" + "\n\n".join(parsed["thought_blocks"]) + "\n\n"
            if parsed.get("final_text_blocks"):
                saved_text += "\n\n".join(parsed["final_text_blocks"])

            if not saved_text.strip():
                saved_text = "Response received (no plain text blocks found)."

            st.session_state.chats[st.session_state.current_chat].append(
                {"role": "assistant", "content": saved_text}
            )
