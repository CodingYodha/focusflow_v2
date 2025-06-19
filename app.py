# app.py
import streamlit as st
import google.generativeai as genai
from datetime import datetime
import json

import calendar_utils
import gamification
import audio_utils

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="FocusFlow - Chat", page_icon="🤖",
    layout="wide", initial_sidebar_state="expanded"
)

# --- FIX: ROBUST SESSION STATE INITIALIZATION ---
# This block runs first and ensures all keys exist before they are accessed.
def initialize_app_state():
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = None
    if "calendar_service" not in st.session_state:
        st.session_state.calendar_service = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_session" not in st.session_state:
        st.session_state.chat_session = None
    gamification.initialize_gamification()

initialize_app_state()

# --- ONBOARDING: Capture user info if not present ---
# The check is now for `is None` since we know the key exists.
if st.session_state.user_profile is None:
    st.title("Welcome to FocusFlow V2! 🚀")
    st.subheader("Let's set up your profile to personalize your experience.")
    
    with st.form("profile_form"):
        name = st.text_input("What should I call you?")
        timezone_options = ["America/New_York", "Europe/London", "Asia/Kolkata", "Asia/Tokyo", "Australia/Sydney"]
        user_timezone = st.selectbox("What is your timezone?", options=timezone_options)
        submitted = st.form_submit_button("Save Profile")
        
        if submitted and name:
            st.session_state.user_profile = {"name": name, "timezone": user_timezone}
            st.success(f"Great to meet you, {name}! Let's get started.")
            st.rerun()
    st.stop()

# --- GEMINI SETUP ---
# Now we set up the chat session only if it hasn't been created yet.
if st.session_state.chat_session is None:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        tools = [calendar_utils.add_event, calendar_utils.get_todays_events, calendar_utils.check_for_conflicts]
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=tools)

        SYSTEM_PROMPT = f"""
        You are FocusFlow, a friendly, encouraging, and highly intelligent AI productivity coach for a student named {st.session_state.user_profile['name']}.
        Your Core Capabilities:
        1. Natural Language Scheduling: You MUST convert natural language into precise data for function calls. When the user says "schedule study time tomorrow from 2pm to 4pm", you must calculate the exact date and convert the times into ISO 8601 format (YYYY-MM-DDTHH:MM:SS). The current date is {datetime.now().strftime('%Y-%m-%d')}. You are responsible for generating the timestamps. DO NOT ask the user for ISO 8601 format.
        2. Conflict Resolution Workflow:
            - Step 1: When a user wants to schedule an event, first determine the start and end times in ISO 8601 format.
            - Step 2: ALWAYS call the `check_for_conflicts` function with these times.
            - Step 3: If `check_for_conflicts` returns a conflict, DO NOT schedule the event. Instead, inform the user about the specific conflict and ask them how to proceed (e.g., "I see you have 'Physics Lecture' then. Should I schedule this new task anyway?").
            - Step 4: Only if `check_for_conflicts` returns "No conflicts found", or if the user explicitly tells you to proceed despite a conflict, should you then call the `add_event` function.
        3. Summarizing the Day: When asked "what's my schedule today?" or similar, use the `get_todays_events` function and present the information clearly.
        4. Personality: Be upbeat, use emojis, and always be supportive. Your goal is to make productivity feel rewarding.
        """
        st.session_state.chat_session = model.start_chat(history=[])
    except Exception as e:
        st.error(f"Error setting up AI model: {e}")
        st.stop()

# --- UI SETUP ---
st.title(f"🤖 Hey, {st.session_state.user_profile['name']}! Let's plan your day.")
gamification.display_gamification_dashboard()

# The check now works correctly because the key is guaranteed to exist.
if st.session_state.calendar_service is None:
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
        # The manual loop for conflict resolution remains the same
        full_prompt = st.session_state.chat_session.history[0].parts[0].text + "\nUser: " + user_prompt if st.session_state.chat_session.history else user_prompt
        response = st.session_state.chat_session.send_message(user_prompt)

        if response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call
            tool_name = function_call.name
            args = {key: value for key, value in function_call.args.items()}
            
            tool_to_call = next((t for t in [calendar_utils.add_event, calendar_utils.get_todays_events, calendar_utils.check_for_conflicts] if t.__name__ == tool_name), None)

            if tool_to_call:
                tool_response = tool_to_call(**args)
                
                response = st.session_state.chat_session.send_message(
                    content=genai.Content(
                        parts=[genai.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=tool_name,
                                response={"result": str(tool_response)}
                            )
                        )]
                    )
                )
                
                if tool_name == "add_event" and "successfully" in str(tool_response):
                     gamification_feedback = gamification.award_xp(gamification.XP_PER_TASK_SCHEDULED, "task")
                     response.parts[0].text += f"\n\n*{gamification_feedback}*"

        assistant_response = response.text
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        st.rerun()

# --- INPUT HANDLING ---
st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    transcribed_text = audio_utils.transcribe_audio_from_mic()
    if transcribed_text:
        process_prompt(transcribed_text)

if text_prompt := st.chat_input("Schedule a task, ask about your day, or just say hi!"):
    process_prompt(text_prompt)