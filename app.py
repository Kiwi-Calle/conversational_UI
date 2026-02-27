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
# 2) Data Agent call (GLOBAL + streaming + retry on transient errors)
# ----------------------------
@st.cache_resource
def get_data_chat_client() -> geminidataanalytics.DataChatServiceClient:
    # Reuse the client across reruns for performance
    return geminidataanalytics.DataChatServiceClient()


def ask_data_agent(user_prompt: str) -> str:
    data_chat_client = get_data_chat_client()

    # Your Google Cloud details
    project_id = "ctrl-digital-ga4"
    location = "global"  # ✅ Conversational Analytics / Data Agents are typically global

    # Your Agent ID
    raw_agent_id = "agent_ae90c1a1-04c1-4cd8-810a-736137d572c4"

    # Clean the ID if a full path/URL was pasted
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

    # Retry transient errors (503 etc.)
    chat_retry = retry.Retry(
        predicate=retry.if_exception_type(
            gexc.ServiceUnavailable,
            gexc.DeadlineExceeded,
            gexc.ResourceExhausted,
        ),
        initial=1.0,
        maximum=20.0,
        multiplier=2.0,
        deadline=120.0,  # total retry window
    )

    try:
        chunks: list[str] = []

        # ✅ Consume server-streaming responses
        for resp in data_chat_client.chat(request=request, timeout=300.0, retry=chat_retry):
            for msg in getattr(resp, "messages", []):
                sys_msg = getattr(msg, "system_message", None)
                if not sys_msg:
                    continue

                # sys_msg.text shape may vary; handle both shapes safely
                text_obj = getattr(sys_msg, "text", None)
                if not text_obj:
                    continue

                text_val = getattr(text_obj, "text", None) if hasattr(text_obj, "text") else text_obj
                if text_val:
                    chunks.append(str(text_val))

        final_answer = "\n".join(chunks).strip()
        return final_answer or "The agent responded, but no text summary was returned."

    except Exception as e:
        return f"Oops! I couldn't reach the Data Agent. Error: {e}"


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
# 6) User input handling
# ----------------------------
if prompt := st.chat_input("Ask about your GA4 data..."):
    # Save user message
    st.session_state.chats[st.session_state.current_chat].append(
        {"role": "user", "content": prompt}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call the agent + display response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data in BigQuery..."):
            response = ask_data_agent(prompt)

        st.markdown(response)
        st.session_state.chats[st.session_state.current_chat].append(
            {"role": "assistant", "content": response}
        )
