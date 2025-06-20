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
        
        # Simplified tool definitions
        add_event_tool = genai.protos.FunctionDeclaration(
            name="add_event",
            description="Adds an event to the user's calendar",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "summary": genai.protos.Schema(
                        type=genai.protos.Type.STRING, 
                        description="Event title"
                    ),
                    "start_time": genai.protos.Schema(
                        type=genai.protos.Type.STRING, 
                        description="Start time in ISO format"
                    ),
                    "end_time": genai.protos.Schema(
                        type=genai.protos.Type.STRING, 
                        description="End time in ISO format"
                    ),
                    "description": genai.protos.Schema(
                        type=genai.protos.Type.STRING, 
                        description="Event description"
                    ),
                },
                required=["summary", "start_time", "end_time"],
            ),
        )

        get_events_tool = genai.protos.FunctionDeclaration(
            name="get_todays_events", 
            description="Gets today's calendar events",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={},
            ),
        )

        tools = genai.protos.Tool(function_declarations=[add_event_tool, get_events_tool])
        
        user_tz_str = st.session_state.user_profile['timezone']
        user_tz = pytz.timezone(user_tz_str)
        current_time = datetime.now(user_tz)
        
        # Simplified and clearer system prompt
        SYSTEM_PROMPT = f"""You are FocusFlow, a calendar assistant for {st.session_state.user_profile['name']}.

Current date/time: {current_time.strftime('%Y-%m-%d %H:%M')} ({user_tz_str})

CRITICAL TIMEZONE RULE: 
- User is in {user_tz_str} timezone
- When user says "8 PM today", that means 8 PM in {user_tz_str}
- Always create times as if they are LOCAL times in {user_tz_str}
- Use simple ISO format without timezone suffix: YYYY-MM-DDTHH:MM:SS

RULES:
1. For scheduling: Call add_event with summary, start_time, end_time 
2. For viewing schedule: Call get_todays_events
3. If info missing, ask briefly

Examples for TODAY ({current_time.strftime('%Y-%m-%d')}):
- "8 PM today" = {current_time.replace(hour=20, minute=0, second=0).strftime('%Y-%m-%dT%H:%M:%S')}
- "2:30 PM today" = {current_time.replace(hour=14, minute=30, second=0).strftime('%Y-%m-%dT%H:%M:%S')}"""
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest", 
            tools=[tools], 
            system_instruction=SYSTEM_PROMPT
        )
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
            raise ValueError("Empty response from AI")
            
        part = response.parts[0]
        
        if part.function_call:
            function_call = part.function_call
            tool_name = function_call.name
            args = dict(function_call.args)
            
            # Add calendar service to args for the functions
            function_map = {
                'add_event': calendar_utils.add_event, 
                'get_todays_events': calendar_utils.get_todays_events
            }
            
            with st.spinner(f"Accessing Google Calendar..."):
                tool_response = function_map[tool_name](**args)
            
            assistant_response = tool_response
            
            # Add gamification for successful task scheduling
            if tool_name == "add_event" and assistant_response.strip().startswith("✅"):
                gamification_feedback = gamification.award_xp(gamification.XP_PER_TASK_SCHEDULED, "task")
                assistant_response += f"\n\n*{gamification_feedback}*"
                
        elif part.text:
            assistant_response = part.text
        else:
            assistant_response = "I received an unusual response. Please try again."
            
    except Exception as e:
        st.error("An error occurred:")
        st.exception(e)
        assistant_response = "I encountered an error. Please try your request again."
    
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

# Handle voice input
if "voice_input_text" not in st.session_state:
    st.session_state.voice_input_text = ""

if st.session_state.voice_input_text:
    prompt_to_process = st.session_state.voice_input_text
    st.session_state.voice_input_text = ""
    process_prompt(prompt_to_process)
    st.rerun()

# Chat input
if text_prompt := st.chat_input("Schedule a task or ask about your day", key="chat_widget"):
    process_prompt(text_prompt)
    st.rerun()

# Voice assistant in sidebar
st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    transcribed_text = audio_utils.transcribe_audio_from_mic()
    if transcribed_text:
        st.session_state.voice_input_text = transcribed_text
        st.rerun()