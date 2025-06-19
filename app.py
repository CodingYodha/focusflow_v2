# app.py
import streamlit as st
import google.generativeai as genai
from datetime import datetime
import datetime as dt
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
        timezone_options = pytz.common_timezones
        user_timezone = st.selectbox("What is your timezone?", options=timezone_options, index=timezone_options.index("UTC"))
        submitted = st.form_submit_button("Save Profile")
        if submitted and name:
            st.session_state.user_profile = {"name": name, "timezone": user_timezone}
            st.rerun()
    st.stop()

if st.session_state.chat_session is None:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # --- FIX 1: Simplify the 'add_event' tool definition ---
        # Make the 'description' parameter optional to reduce the chance of a malformed call.
        add_event_tool = genai.protos.FunctionDeclaration(
            name="add_event",
            description="Adds an event to the user's calendar after checking for conflicts.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "summary": genai.protos.Schema(type=genai.protos.Type.STRING, description="The title of the event, e.g., 'Study Session' or 'Team Meeting'."),
                    "start_time": genai.protos.Schema(type=genai.protos.Type.STRING, description="The start time in full ISO 8601 format with timezone offset."),
                    "end_time": genai.protos.Schema(type=genai.protos.Type.STRING, description="The end time in full ISO 8601 format with timezone offset."),
                    "description": genai.protos.Schema(type=genai.protos.Type.STRING, description="An optional, more detailed description for the event."),
                },
                required=["summary", "start_time", "end_time"],
            ),
        )

        get_events_tool = genai.protos.FunctionDeclaration(name="get_todays_events", description="Fetches all events scheduled for the current day from the user's calendar.")

        tools = genai.protos.Tool(function_declarations=[add_event_tool, get_events_tool])
        
        user_tz_str = st.session_state.user_profile['timezone']
        user_tz = pytz.timezone(user_tz_str)
        tz_offset = datetime.now(user_tz).strftime('%z')
        tz_offset_formatted = f"{tz_offset[:-2]}:{tz_offset[-2:]}"

        # --- FIX 2: More Direct and Forceful System Prompt ---
        SYSTEM_PROMPT = f"""
        You are a function-calling AI model named FocusFlow. You serve a student named {st.session_state.user_profile['name']}.
        Your user's timezone is `{user_tz_str}`. The current date is {datetime.now().strftime('%Y-%m-%d')}.

        **PRIMARY DIRECTIVE: Your ONLY purpose is to call functions. Do not have conversations.**

        **RULE 1: SCHEDULING**
        - If the user's prompt includes words like 'schedule', 'create', 'add', 'plan', or mentions a time and an activity, you MUST call the `add_event` function.
        - You MUST infer the `summary` from the user's prompt (e.g., for "plan a study session", summary is "Study Session").
        - You MUST calculate the `start_time` and `end_time` in the exact ISO 8601 format: `YYYY-MM-DDTHH:MM:SS{tz_offset_formatted}`.
        - If any required information (`summary`, `start_time`, `end_time`) is missing, you MUST ask the user for ONLY the missing information. DO NOT respond with a generic message. Example: "What should I call this event?" or "What time does this event start?".

        **RULE 2: VIEWING SCHEDULE**
        - If the user's prompt includes words like 'schedule', 'what's on', 'my day', 'am I busy', you MUST call the `get_todays_events` function.

        **RULE 3: NO GENERIC ANSWERS**
        - You are forbidden from answering a scheduling or viewing request with plain text. You must always attempt a function call.
        """
        
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[tools], system_instruction=SYSTEM_PROMPT)
        st.session_state.chat_session = model.start_chat(history=[])
    except Exception as e:
        st.error(f"Error setting up AI model: {e}")
        st.exception(e)
        st.stop()

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
            raise ValueError("The AI returned an empty response. This could be due to a content filter.")
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

if "voice_input_text" not in st.session_state:
    st.session_state.voice_input_text = ""

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