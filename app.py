# app.py
import streamlit as st
import google.generativeai as genai
from datetime import datetime
import pytz

import calendar_utils
import gamification
import audio_utils

st.set_page_config(page_title="FocusFlow - Chat", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

def initialize_app_state():
    if "user_profile" not in st.session_state: st.session_state.user_profile = None
    if "calendar_service" not in st.session_state: st.session_state.calendar_service = None
    if "messages" not in st.session_state: st.session_state.messages = []
    if "chat_session" not in st.session_state: st.session_state.chat_session = None
    if "voice_input_text" not in st.session_state: st.session_state.voice_input_text = ""
    gamification.initialize_gamification()

initialize_app_state()

if st.session_state.user_profile is None:
    st.title("Welcome to FocusFlow V2! 🚀")
    with st.form("profile_form"):
        name = st.text_input("What should I call you?")
        # Using the full list of pytz timezones for user selection
        timezone_options = pytz.common_timezones
        default_index = timezone_options.index('Asia/Kolkata') if 'Asia/Kolkata' in timezone_options else 0
        user_timezone = st.selectbox("What is your timezone?", options=timezone_options, index=default_index)
        submitted = st.form_submit_button("Save Profile")
        if submitted and name:
            st.session_state.user_profile = {"name": name, "timezone": user_timezone}
            st.rerun()
    st.stop()

if st.session_state.chat_session is None:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # --- FIX: The AI now works with NAIVE time strings ---
        add_event_tool = genai.protos.FunctionDeclaration(
            name="add_event",
            description="Adds an event to the user's calendar.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "summary": genai.protos.Schema(type=genai.protos.Type.STRING, description="The title of the event."),
                    "start_time_str": genai.protos.Schema(type=genai.protos.Type.STRING, description="The start time as a timezone-NAIVE string in `YYYY-MM-DDTHH:MM:SS` format."),
                    "end_time_str": genai.protos.Schema(type=genai.protos.Type.STRING, description="The end time as a timezone-NAIVE string in `YYYY-MM-DDTHH:MM:SS` format."),
                    "description": genai.protos.Schema(type=genai.protos.Type.STRING, description="An optional description."),
                },
                required=["summary", "start_time_str", "end_time_str"],
            ),
        )
        get_events_tool = genai.protos.FunctionDeclaration(name="get_todays_events", description="Fetches all events for today.")
        tools = genai.protos.Tool(function_declarations=[add_event_tool, get_events_tool])
        
        # --- FIX: REWRITTEN SYSTEM PROMPT FOR NAIVE TIME ---
        SYSTEM_PROMPT = f"""
        You are an expert, function-calling AI model. Your sole purpose is to convert user requests into function calls.
        The current date is {datetime.now().strftime('%Y-%m-%d')}.

        **CRITICAL, UNBREAKABLE RULES FOR SCHEDULING:**
        1.  When a user asks to schedule an event (e.g., "schedule study time tomorrow from 4pm to 7pm"), you MUST call the `add_event` function.
        2.  You MUST calculate the date and time based on the user's prompt.
        3.  The `start_time_str` and `end_time_str` parameters MUST be strings in the **exact timezone-NAIVE ISO 8601 format**.
        4.  **CORRECT FORMAT:** `YYYY-MM-DDTHH:MM:SS`
        5.  **EXAMPLE:** If the user asks to schedule something for 4:00 PM today, your `start_time_str` argument would be `{datetime.now().strftime('%Y-%m-%d')}T16:00:00`.
        6.  **DO NOT include any timezone information (like 'Z' or '+05:30') in the time strings.**
        7.  You MUST infer the `summary` from the user's prompt.
        8.  If any required information is missing, you MUST ask the user for ONLY the missing information.

        **RULE FOR VIEWING SCHEDULE:**
        - If the user asks to see their schedule, you MUST call the `get_todays_events` function.
        """
        
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[tools], system_instruction=SYSTEM_PROMPT)
        st.session_state.chat_session = model.start_chat(history=[])
    except Exception as e:
        st.error(f"Error setting up AI model: {e}")
        st.exception(e)
        st.stop()

# The rest of the app logic remains the same as the previous correct version.
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

def process_prompt(user_prompt):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    try:
        with st.spinner("Thinking..."):
            response = st.session_state.chat_session.send_message(user_prompt)
        if not response.parts:
            raise ValueError("The AI returned an empty response.")
        part = response.parts[0]
        if part.function_call:
            function_call = part.function_call
            tool_name = function_call.name
            args = dict(function_call.args)
            function_map = {'add_event': calendar_utils.add_event, 'get_todays_events': calendar_utils.get_todays_events}
            with st.spinner(f"Accessing Google Calendar to {tool_name.replace('_', ' ')}..."):
                tool_response = function_map[tool_name](**args)
            assistant_response = tool_response
            if tool_name == "add_event" and assistant_response.strip().startswith("✅"):
                gamification_feedback = gamification.award_xp(gamification.XP_PER_TASK_SCHEDULED, "task")
                assistant_response += f"\n\n*{gamification_feedback}*"
        elif part.text:
            assistant_response = part.text
        else:
            assistant_response = "I received an unusual response from the AI. Please try again."
    except Exception as e:
        st.error("An unexpected error occurred. See details below.")
        st.exception(e)
        assistant_response = "I ran into a problem and couldn't complete your request."
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

if st.session_state.voice_input_text:
    prompt_to_process = st.session_state.voice_input_text
    st.session_state.voice_input_text = ""
    process_prompt(prompt_to_process)
    st.rerun()

if text_prompt := st.chat_input("Schedule a task or ask about your day", key="chat_widget"):
    process_prompt(text_prompt)
    st.rerun()

st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    transcribed_text = audio_utils.transcribe_audio_from_mic()
    if transcribed_text:
        st.session_state.voice_input_text = transcribed_text
        st.rerun()