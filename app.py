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
    
    # Your specific Google Cloud details
    project_id = "ctrl-digital-ga4"
    location = "europe-north2"
    raw_agent_id = "agent_ae90c1a1-04c1-4cd8-810a-736137d572c4" 
    
    # Clean the ID just in case you pasted the full URL path
    if "/" in raw_agent_id:
        clean_agent_id = raw_agent_id.split("/")[-1]
    else:
        clean_agent_id = raw_agent_id

    # Format the Agent Path safely
    agent_path = data_chat_client.data_agent_path(project_id, location, clean_agent_id)
    
    # Package the user's prompt
    messages = [
        geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=user_prompt)
        )
    ]
    
    # Build the final request (with data_agent_context correctly attached!)
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id}/locations/{location}",
        messages=messages,
        data_agent_context=geminidataanalytics.DataAgentContext(
            data_agent=agent_path
        )
    )
    
    try:
        # Send the question to Google
        response = data_chat_client.chat(request=request)
        
        # Extract the plain text answer from the agent
        final_answer = ""
        for msg in response.messages:
            # Check if the message came from the system/agent and contains text
            if getattr(msg, "system_message", None) and getattr(msg.system_message, "text", None):
                final_answer += str(getattr(msg.system_message.text, "text", msg.system_message.text)) + "\n"
                
        return final_answer if final_answer else "The agent processed the request, but didn't return a text summary."
        
    except Exception as e:
        return f"Oops! I couldn't reach the Data Agent. Error: {e}"

# 4. Initialize Multiple Chats in Session State
if "chats" not in st.session_state:
    st.session_state.chats = {"Conversation 1": []}
if "current_chat" not in st
