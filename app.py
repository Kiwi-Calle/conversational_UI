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
    """
    Best-effort extractor for different SDK text shapes.
    Returns "" if it can't find a text value.
    """
    if obj is None:
        return ""

    if isinstance(obj, str):
        return obj

    # Common shapes: obj.text (string) OR obj.text.text
    t = getattr(obj, "text", None)
    if isinstance(t, str):
        return t

    if t is not None:
        t2 = getattr(t, "text", None)
        if isinstance(t2, str):
            return t2

    return ""


def _to_dict(proto_obj) -> dict:
    """
    Convert protobuf message to a JSON-serializable dict (best effort).
    This lets us always show "whatever the agent returned".
    """
    try:
        pb = getattr(proto_obj, "_pb", proto_obj)
        return MessageToDict(pb, preserving_proto_field_name=True)
    except Exception:
        return {"repr": repr(proto_obj)}


@st.cache_resource
def get_data_chat_client() -> geminidataanalytics.DataChatServiceClient:
    # Reuse the client across reruns for performance
    return geminidataanalytics.DataChatServiceClient()


def stream_data_agent_with_raw(user_prompt: str):
    """
    Stream the Data Agent response.
    Yields tuples: (text_chunk: str, raw_message_dict: dict)

    text_chunk may be "" if the response is structured/non-text.
    raw_message_dict is always provided (best effort).
    """
    data_chat_client = get_data_chat_client()

    # Your Google Cloud details
    project_id = "ctrl-digital-ga4"
    location = "global"  # ✅ Conversational Analytics / Data Agents are typically global

    # Your Agent ID
    raw_agent_id = "agent_ae90c1a1-04c1-4cd8-810a-736137d572c4"
    clean_agent_id = raw_agent_id.split("/")[-1]

    # Build the agent resource path
    agent_path = data_chat_client.data_agent_path(project_id, location, clean_agent_id)

    # Build request
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id}/locations/{location}",
        messages=[
            geminidataanalytics.Message(
                user_message=geminidataanalytics.UserMessage(text=user_prompt)
            )
        ],
        data_agent_context=geminidataanalytics.DataAgentContext(data_agent=agent_path),
    )

    # Retry transient errors
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

    # Stream responses
    for resp in data_chat_client.chat(request=request, timeout=300.0, retry=chat_retry):
        # Some SDK variants return response chunks containing a list of messages
        for msg in getattr(resp, "messages", []):
            msg_dict = _to_dict(msg)

            # Prefer assistant_message, fallback to system_message
            a_msg = getattr(msg, "assistant_message", None)
            s_msg = getattr(msg, "system_message", None)

            txt = ""
            if a_msg:
                txt = _extract_text(getattr(a_msg, "text", a_msg))
            if not txt and s_msg:
                txt = _extract_text(getattr(s_msg, "text", s_msg))

            yield (txt, msg_dict)

        # If resp unexpectedly has no messages, still yield raw resp dict once
        if not getattr(resp, "messages", None):
            yield ("", _to_dict(resp))


# ----------------------------
# 3) Multi-chat session state
# ----------------------------
if "chats" not in st.session_state:
    st.session_state.chats = {"Conversation 1": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Conversation 1"

# Optional UI toggle to always show raw output for debugging
if "show_raw" not in st.session_state:
    st.session_state.show_raw = False

# ----------------------------
# 4) Sidebar (chat history + debug toggle)
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

    st.divider()
    st.session_state.show_raw = st.toggle("Show raw agent output (debug)", value=st.session_state.show_raw)

# ----------------------------
# 5) Main chat UI
# ----------------------------
st.title(f"📊 {st.session_state.current_chat}")

current_messages = st.session_state.chats[st.session_state.current_chat]
for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ----------------------------
# 6) User input handling (STREAM text if possible, otherwise SHOW RAW)
# ----------------------------
if prompt := st.chat_input("Ask about your GA4 data..."):
    # Save user message
    st.session_state.chats[st.session_state.current_chat].append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant response area
    with st.chat_message("assistant"):
        text_placeholder = st.empty()
        raw_placeholder = st.empty()

        full_text = ""
        raw_messages = []
        saw_text = False

        try:
            with st.spinner("Analyzing data in BigQuery..."):
                for text_chunk, raw_msg in stream_data_agent_with_raw(prompt):
                    raw_messages.append(raw_msg)

                    # Stream text if present
                    if text_chunk:
                        saw_text = True
                        full_text += text_chunk
                        text_placeholder.markdown(full_text)

                    # Optionally live-show the latest raw message while streaming
                    if st.session_state.show_raw:
                        raw_placeholder.json(raw_msg)

            # If we got text, finalize
            if saw_text and full_text.strip():
                text_placeholder.markdown(full_text)

                # If debug toggle is on, show all raw messages at the end too (capped)
                if st.session_state.show_raw:
                    raw_placeholder.json(raw_messages[:50])

                # Save assistant message (text) to history
                st.session_state.chats[st.session_state.current_chat].append(
                    {"role": "assistant", "content": full_text}
                )

            else:
                # No text found — show raw output as the "answer"
                text_placeholder.markdown(
                    "No plain text was returned. Showing raw agent output below:"
                )
                raw_placeholder.json(raw_messages[:50])  # cap to keep UI responsive

                # Offer download of full raw output
                raw_json_str = json.dumps(raw_messages, indent=2, ensure_ascii=False)
                st.download_button(
                    "Download full raw response (JSON)",
                    data=raw_json_str,
                    file_name="agent_response.json",
                    mime="application/json",
                    use_container_width=True,
                )

                # Save a placeholder entry to history
                st.session_state.chats[st.session_state.current_chat].append(
                    {"role": "assistant", "content": "No plain text returned; raw output shown."}
                )

        except Exception as e:
            err = f"Oops! I couldn't reach the Data Agent. Error: {e}"
            text_placeholder.markdown(err)
            st.session_state.chats[st.session_state.current_chat].append(
                {"role": "assistant", "content": err}
            )
