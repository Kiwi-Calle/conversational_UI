import streamlit as st
# The CORRECT library for BigQuery Data Agents
from google.cloud import geminidataanalytics 

# ... (Keep your CSS setup here) ...

def ask_data_agent(user_prompt):
    # Initialize the correct client
    data_chat_client = geminidataanalytics.DataChatServiceClient()
    
    # Set your exact details
    project_id = "ctrl-digital-ga4"
    location = "europe-north2"
    # MAKE SURE TO PASTE YOUR ACTUAL AGENT ID HERE
    agent_id = "agent_ae90c1a1-04c1-4cd8-810a-736137d572c4" 
    
    # 1. Format the Agent Path
    agent_path = data_chat_client.data_agent_path(project_id, location, agent_id)
    
    # 2. Package the user's prompt
    messages = [
        geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=user_prompt)
        )
    ]
    
    # 3. Tell the API which agent to talk to
    conversation_reference = geminidataanalytics.ConversationReference(
        data_agent_context=geminidataanalytics.DataAgentContext(
            data_agent=agent_path
        )
    )
    
    # 4. Build the final request
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id}/locations/{location}",
        messages=messages,
        conversation_reference=conversation_reference
    )
    
    try:
        # Send it to Google!
        response = data_chat_client.chat(request=request)
        
        # Extract the text answer from the response
        final_answer = ""
        for msg in response.messages:
            if getattr(msg, "system_message", None) and getattr(msg.system_message, "text", None):
                # We grab the final text from the agent
                final_answer += str(getattr(msg.system_message.text, "text", msg.system_message.text)) + "\n"
                
        return final_answer if final_answer else "Agent responded, but didn't return plain text."
        
    except Exception as e:
        return f"Oops! I couldn't reach the Data Agent. Error: {e}"

# ... (Keep your chat UI code down here) ...
