# app.py
import streamlit as st
import google.generativeai as genai
from datetime import datetime
import json

import calendar_utils
import gamification
import audio_utils

# --- PAGE CONFIGURATION & INITIALIZATION ---
st.set_page_config(
    page_title="FocusFlow - Chat", page_icon="🤖",
    layout="wide", initial_sidebar_state="expanded"
)

# Initialize gamification state early
gamification.initialize_gamification()

# --- ONBOARDING: Capture user info if not present ---
if "user_profile" not in st.session_state:
    st.title("Welcome to FocusFlow V2! 🚀")
    st.subheader("Let's set up your profile to personalize your experience.")
    
    with st.form("profile_form"):
        name = st.text_input("What should I call you?")
        timezone_options = ["America/New_York", "Europe/London", "Asia/Kolkata", "Asia/Tokyo", "Australia/Sydney"] # Add more as needed
        user_timezone = st.selectbox("What is your timezone?", options=timezone_options)
        submitted = st.form_submit_button("Save Profile")
        
        if submitted and name:
            st.session_state.user_profile = {"name": name, "timezone": user_timezone}
            st.success(f"Great to meet you, {name}! Let's get started.")
            st.rerun()
    st.stop()

# --- GEMINI SETUP ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    
    # We now define tools with specific functions for better control
    tools = [
        calendar_utils.add_event,
        calendar_utils.get_todays_events,
        calendar_utils.check_for_conflicts
    ]
    model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=tools)

    # POWERFUL NEW SYSTEM PROMPT
    SYSTEM_PROMPT = f"""
    You are FocusFlow, a friendly, encouraging, and highly intelligent AI productivity coach for a student named {st.session_state.user_profile['name']}.

    Your Core Capabilities:
    1.  **Natural Language Scheduling**: You MUST convert natural language into precise data for function calls.
        -   When the user says "schedule study time tomorrow from 2pm to 4pm", you must calculate the exact date and convert the times into ISO 8601 format (YYYY-MM-DDTHH:MM:SS) before calling any function. The current date is {datetime.now().strftime('%Y-%m-%d')}.
        -   You are responsible for generating the timestamps. DO NOT ask the user for ISO 8601 format.
    
    2.  **Conflict Resolution Workflow**:
        -   **Step 1**: When a user wants to schedule an event, first determine the start and end times in ISO 8601 format.
        -   **Step 2**: ALWAYS call the `check_for_conflicts` function with these times.
        -   **Step 3**: If `check_for_conflicts` returns a conflict, DO NOT schedule the event. Instead, inform the user about the specific conflict and ask them how to proceed (e.g., "I see you have 'Physics Lecture' then. Should I schedule this new task anyway?").
        -   **Step 4**: Only if `check_for_conflicts` returns "No conflicts found", or if the user explicitly tells you to proceed despite a conflict, should you then call the `add_event` function.

    3.  **Summarizing the Day**: When asked "what's my schedule today?" or similar, use the `get_todays_events` function and present the information clearly.

    4.  **Personality**: Be upbeat, use emojis, and always be supportive. Your goal is to make productivity feel rewarding.
    """
    
    chat = model.start_chat(history=[]) # Start with empty history

except Exception as e:
    st.error(f"Error setting up AI model: {e}")
    st.stop()

# --- SESSION STATE & UI SETUP ---
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_session" not in st.session_state: st.session_state.chat_session = chat

st.title(f"🤖 Hey, {st.session_state.user_profile['name']}! Let's plan your day.")
gamification.display_gamification_dashboard()

if st.session_state.calendar_service is None:
    # Authentication logic remains the same...
    st.info("Please authenticate with Google Calendar to unlock scheduling features.")
    if st.button("Login with Google"):
        with st.spinner("Authenticating..."):
            st.session_state.calendar_service = calendar_utils.authenticate_google_calendar()
            st.rerun()
    st.stop()

# --- CHAT DISPLAY & PROCESSING ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def process_prompt(user_prompt):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.spinner("Thinking..."):
        # We now use a manual loop to handle the conflict resolution logic
        full_prompt = SYSTEM_PROMPT + "\nUser: " + user_prompt
        response = st.session_state.chat_session.send_message(full_prompt)

        # Check for function calls
        if response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call
            tool_name = function_call.name
            args = {key: value for key, value in function_call.args.items()}
            
            # Find the actual python function
            tool_to_call = next((t for t in tools if t.__name__ == tool_name), None)

            if tool_to_call:
                tool_response = tool_to_call(**args)
                
                # Send the tool response back to the model
                response = st.session_state.chat_session.send_message(
                    content=genai.Content(
                        parts=[genai.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response={"result": tool_response}
                            )
                        )]
                    )
                )
                
                # Special handling after add_event is called
                if tool_name == "add_event" and "successfully" in tool_response:
                     gamification_feedback = gamification.award_xp(gamification.XP_PER_TASK_SCHEDULED, "task")
                     response.parts[0].text += f"\n\n*{gamification_feedback}*"

        assistant_response = response.text
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        st.rerun()

# --- INPUT HANDLING (TEXT & VOICE) ---
# Voice Input
st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    transcribed_text = audio_utils.transcribe_audio_from_mic()
    if transcribed_text:
        process_prompt(transcribed_text)

# Text Input
if text_prompt := st.chat_input("Schedule a task, ask about your day, or just say hi!"):
    process_prompt(text_prompt)