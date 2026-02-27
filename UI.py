import streamlit as st
from google.cloud import discoveryengine_v1alpha as discoveryengine # ADDED: Import the Google Cloud API library

# 1. Set up the page
st.set_page_config(page_title="Conversational Agent", page_icon="📊", layout="wide")

# 2. Inject Custom CSS for the Background
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

# --- ADDED: The Function that talks to your Data Agent ---
def ask_data_agent(user_prompt):
    # Initialize the client
    client = discoveryengine.ConversationalSearchServiceClient()
    
    # YOUR SPECIFIC AGENT RESOURCE NAME
    # Replace YOUR_AGENT_ID with the actual ID from your console
    agent_resource_name = "projects/ctrl-digital-ga4/locations/europe-north2/agents/agent_ae90c1a1-04c1-4cd8-810a-736137d572c4"
    
    # Format the request
    request = discoveryengine.ConverseConversationRequest(
        name=agent_resource_name,
        query=discoveryengine.TextInput(input=user_prompt)
    )
    
    try:
        # Send the question to Google
        response = client.converse_conversation(request=request)
        # Extract the text answer provided by the Data Agent
        return response.reply.summary.summary_text
    except Exception as e:
        return f"Oops! I couldn't reach the Data Agent. Error: {e}"
# ---------------------------------------------------------

# 3. Initialize Multiple Chats in Session State
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

    # --- UPDATED: Call the Real API instead of simulating it ---
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data in BigQuery..."):
            
            # Send the prompt to the new function
            response = ask_data_agent(prompt)
            
            # Display and save the real answer
            st.markdown(response)
            st.session_state.chats[st.session_state.current_chat].append({"role": "assistant", "content": response})
    # -----------------------------------------------------------
