import streamlit as st

# 1. Set up the page
st.set_page_config(page_title="Conversational Agent", page_icon="📊", layout="wide")

# 2. Inject Custom CSS for the Background
# You can change the hex code (#f0f4f8) to any color you like, or even use an image URL!
st.markdown(
    """
    <style>
    .stApp {
        background-color: #36454F; 
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Initialize Multiple Chats in Session State
# Instead of one list, we use a dictionary to hold multiple lists of messages
if "chats" not in st.session_state:
    st.session_state.chats = {"Conversation 1": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Conversation 1"

# 4. Build the Sidebar
with st.sidebar:
    st.title("💬 Chat History")
    
    # Button to create a new chat
    if st.button("➕ New Conversation", use_container_width=True):
        new_chat_name = f"Conversation {len(st.session_state.chats) + 1}"
        st.session_state.chats[new_chat_name] = []
        st.session_state.current_chat = new_chat_name
        st.rerun() # Refreshes the UI to show the new chat

    st.divider()

    # Create a button for every existing chat in our dictionary
    for chat_name in st.session_state.chats.keys():
        # Highlight the active chat visually
        is_active = "✅ " if chat_name == st.session_state.current_chat else ""
        if st.button(f"{is_active}{chat_name}", use_container_width=True):
            st.session_state.current_chat = chat_name
            st.rerun()

# 5. Main Chat Interface
st.title(f"📊 {st.session_state.current_chat}")

# Load messages only for the currently selected chat
current_messages = st.session_state.chats[st.session_state.current_chat]

for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 6. Handle User Input
if prompt := st.chat_input("Ask about your data"):
    
    # Save to the specific active chat
    st.session_state.chats[st.session_state.current_chat].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Simulated API Response
    with st.chat_message("assistant"):
        response = f"I am looking up data for '{prompt}' in {st.session_state.current_chat}..."
        st.markdown(response)
        st.session_state.chats[st.session_state.current_chat].append({"role": "assistant", "content": response})
