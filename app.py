import streamlit as st
from google.cloud import geminidataanalytics
from google.api_core import retry
from google.api_core import exceptions as gexc

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

    # Common shapes: .text (string) OR .text.text
    t = getattr(obj, "text", None)
    if isinstance(t, str):
        return t

    if t is not None:
        t2 = getattr(t, "text", None)
        if isinstance(t2, str):
            return t2

    return ""


@st.cache_resource
def get_data_chat_client() -> geminidataanalytics.DataChatServiceClient:
    # Reuse the client across reruns for performance
    return geminidataanalytics.DataChatServiceClient()


def stream_data_agent(user_prompt: str):
    """
    Yields text chunks as they arrive from the Data Agent (server-streaming).
    """
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

    # Stream responses
    for resp in data_chat_client.chat(request=request, timeout=300.0, retry=chat_retry):
        for msg in getattr(resp, "messages", []):
            # Prefer assistant_message, fallback to system_message
            a_msg = getattr(msg, "assistant_message", None)
            s_msg = getattr(msg, "system_message", None)

            txt = ""
            if a_msg:
                txt = _extract_text(getattr(a_msg, "text", a_msg))
            if not txt and s_msg:
                txt = _extract_text(getattr(s_msg, "text", s_msg))

            if txt:
                yield txt


# ----------------------------
# 3) Multi-chat session state
# ----------------------------
if "chats" not in st.session_state:
    st.session_state.chats = {"Conversation 1": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Conversation 1"

# ----------------------------
# 4) Sidebar (chat history)
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
# 5) Main chat UI
# ----------------------------
st.title(f"📊 {st.session_state.current_chat}")

current_messages = st.session_state.chats[st.session_state.current_chat]
for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ----------------------------
# 6) User input handling (STREAMING OUTPUT)
# ----------------------------
if prompt := st.chat_input("Ask about your GA4 data..."):
    # Save user message
    st.session_state.chats[st.session_state.current_chat].append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # Stream assistant response
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""

        try:
            with st.spinner("Analyzing data in BigQuery..."):
                for chunk in stream_data_agent(prompt):
                    # Append as it streams
                    full_text += chunk
                    placeholder.markdown(full_text)

            # If nothing came back, show a helpful fallback
            if not full_text.strip():
                full_text = "The agent responded, but no text output was returned."
                placeholder.markdown(full_text)

        except Exception as e:
            full_text = f"Oops! I couldn't reach the Data Agent. Error: {e}"
            placeholder.markdown(full_text)

    # Save assistant message
    st.session_state.chats[st.session_state.current_chat].append(
        {"role": "assistant", "content": full_text}
    )
