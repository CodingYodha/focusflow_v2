# app.py
# Imports and page config are the same...
import streamlit as st
import google.generativeai as genai
from datetime import datetime
import json
import datetime as dt

import calendar_utils
import gamification
import audio_utils

st.set_page_config(
    page_title="FocusFlow - Chat", page_icon="🤖",
    layout="wide", initial_sidebar_state="expanded"
)

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

if st.session_state.user_profile is None:
    # Onboarding logic is the same...
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

if st.session_state.chat_session is None:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        tools = [calendar_utils.add_event, calendar_utils.get_todays_events, calendar_utils.check_for_conflicts]
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=tools)
        
        # --- FIX 3: MORE EXPLICIT SYSTEM PROMPT ---
        user_tz = st.session_state.user_profile['timezone']
        tz_offset = datetime.now(dt.timezone.utc).astimezone().strftime('%z')
        
        SYSTEM_PROMPT = f"""
        You are FocusFlow, an expert AI productivity coach for {st.session_state.user_profile['name']}.
        Your timezone is {user_tz}. The current date is {datetime.now().strftime('%Y-%m-%d')}.

        **CRITICAL INSTRUCTION FOR SCHEDULING:**
        When you call the `add_event` function, the `start_time` and `end_time` parameters MUST be in the full ISO 8601 format including the timezone offset.
        -   **Correct Format**: `YYYY-MM-DDTHH:MM:SS-HH:MM` or `YYYY-MM-DDTHH:MM:SS+HH:MM`
        -   **Example**: For 3 PM today in a timezone 4 hours behind UTC, the format is `2024-08-04T15:00:00-04:00`.
        -   The current user's timezone offset is `{tz_offset}`. You MUST use this offset.
        -   **You are responsible for calculating this full timestamp. DO NOT ask the user for it.** Convert all natural language times (e.g., "3pm tomorrow", "next Tuesday at noon") into this exact format.

        **Conflict Resolution Workflow:**
        -   Step 1: Calculate the full ISO 8601 start and end times based on the user's request.
        -   Step 2: ALWAYS call `check_for_conflicts` with these exact timestamps.
        -   Step 3: If a conflict exists, inform the user and ask how to proceed.
        -   Step 4: Only call `add_event` if there are no conflicts or the user confirms to schedule anyway.

        **Other Capabilities:**
        -   To check the schedule, use `get_todays_events`.
        -   Maintain a friendly, encouraging, emoji-filled personality.
        """
        st.session_state.chat_session = model.start_chat(history=[])
    except Exception as e:
        st.error(f"Error setting up AI model: {e}")
        st.stop()

# --- UI, Authentication, and Chat History display logic remains the same ---
st.title(f"🤖 Hey, {st.session_state.user_profile['name']}! Let's plan your day.")
gamification.display_gamification_dashboard()

if st.session_state.calendar_service is None:
    st.info("Please authenticate with Google Calendar to unlock scheduling features.")
    if st.button("Login with Google"):
        with st.spinner("Authenticating..."):
            st.session_state.calendar_service = calendar_utils.authenticate_google_calendar()
            st.rerun()
    st.stop()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- The rest of the app.py (process_prompt, input handling) is the same ---
def process_prompt(user_prompt):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.spinner("Thinking..."):
        try:
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
        except Exception as e:
            st.error(f"An error occurred: {e}")
            assistant_response = "Sorry, I ran into a problem. Please try rephrasing your request."

        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        st.rerun()

st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    transcribed_text = audio_utils.transcribe_audio_from_mic()
    if transcribed_text:
        process_prompt(transcribed_text)

if text_prompt := st.chat_input("Schedule a task, ask about your day, or just say hi!"):
    process_prompt(text_prompt)