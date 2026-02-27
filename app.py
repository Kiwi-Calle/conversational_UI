import streamlit as st
from google.cloud import geminidataanalytics

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

# 3. The Function that talks to your BigQuery Data Agent
def ask_data_agent(user_prompt):
    # Initialize the correct client for BigQuery Agents
    data_chat_client = geminidataanalytics.DataChatServiceClient()
    
    project_id = "ctrl-digital-ga4"
    location = "europe-north2"
    
    # Paste whatever you have here (full string or just the ID)
    raw_agent_id = "agent_ae90c1a1-04c1-4cd8-810a-736137d572c4" 
    
    # --- NEW: Automatically clean the ID just in case! ---
    if "/" in raw_agent_id:
        clean_agent_id = raw_agent_id.split("/")[-1]
    else:
        clean_agent_id = raw_agent_id
    # -----------------------------------------------------

    # Format the Agent Path using the cleaned ID
    agent_path = data_chat_client.data_agent_path(project_id, location, clean_agent_id)
    
    # Package the user's prompt
    messages = [
        geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=user_prompt)
        )
    ]
    
    # Tell the API which agent to talk to
    conversation_reference = geminidataanalytics.ConversationReference(
        data_agent_context=geminidataanalytics.DataAgentContext(
            data_agent=agent_path
        )
    )
    
    # Build the final request
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id}/locations/{location}",
        messages=messages,
        conversation_reference=conversation_reference
    )
    
    try:
        response = data_chat_client.chat(request=request)
        
        final_answer = ""
        for msg in response.messages:
            if getattr(msg, "system_message", None) and getattr(msg.system_message, "text", None):
                final_answer += str(getattr(msg.system_message.text, "text", msg.system_message.text)) + "\n"
                
        return final_answer if final_answer else "The agent processed the request, but didn't return a text summary."
        
    except Exception as e:
        return f"Oops! I couldn't reach the Data Agent. Error: {e}"

# 4. Initialize Multiple Chats in Session State
if "chats" not in st.session_state:
    st.session_state.chats = {"Conversation 1": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Conversation 1"

# 5. Build the Sidebar
with st.sidebar:
    st.title("💬 Chat History")
    
    # Button to create a new chat
    if st.button("➕ New Conversation", use_container_width=True):
        new_chat_name = f"Conversation {len(st.session_state.chats) + 1}"
        st.session_state.chats[new_chat_name] = []
        st.session_state.current_chat = new_chat_name
        st.rerun() # Refreshes the UI

    st.divider()

    # Create a button for every existing chat
    for chat_name in st.session_state.chats.keys():
        is_active = "✅ " if chat_name == st.session_state.current_chat else ""
        if st.button(f"{is_active}{chat_name}", use_container_width=True):
            st.session_state.current_chat = chat_name
            st.rerun()

# 6. Main Chat Interface
st.title(f"📊 {st.session_state.current_chat}")

# Load messages only for the currently selected chat
current_messages = st.session_state.chats[st.session_state.current_chat]

for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 7. Handle User Input
if prompt := st.chat_input("Ask about your data"):
    
    # Save to the specific active chat
    st.session_state.chats[st.session_state.current_chat].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call the Real API
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data in BigQuery..."):
            
            # Send the prompt to the API function
            response = ask_data_agent(prompt)
            
            # Display and save the real answer
            st.markdown(response)
            st.session_state.chats[st.session_state.current_chat].append({"role": "assistant", "content": response})
