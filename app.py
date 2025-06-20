# app.py
import streamlit as st
import google.generativeai as genai
from datetime import datetime
import pytz
import os

# Import from the new 'core' directory
from core import calendar_utils, gamification_utils, audio_utils

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FocusFlow - Chat", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

# --- ROBUST SESSION STATE INITIALIZATION ---
def initialize_app_state():
    """Initializes all required session state variables to prevent errors on first run."""
    if "user_profile" not in st.session_state: st.session_state.user_profile = None
    if "calendar_service" not in st.session_state: st.session_state.calendar_service = None
    if "messages" not in st.session_state: st.session_state.messages = []
    if "chat_session" not in st.session_state: st.session_state.chat_session = None
    if "voice_input_text" not in st.session_state: st.session_state.voice_input_text = ""
    # Make sure the gamification state is also initialized
    if "xp" not in st.session_state:
        gamification_utils.initialize_gamification()

initialize_app_state()

# --- ONBOARDING WIDGET ---
if st.session_state.user_profile is None:
    st.title("Welcome to FocusFlow V2! 🚀")
    st.subheader("Let's set up your profile to enable all features.")
    with st.form("profile_form"):
        name = st.text_input("What's your name?")
        # CRITICAL: Phone number is the unique ID for the voice agent
        phone_number = st.text_input("What's your phone number? (in E.164 format, e.g., +919876543210)", help="This is required to use the voice agent.")
        
        timezone_options = pytz.common_timezones
        default_index = timezone_options.index('Asia/Kolkata') if 'Asia/Kolkata' in timezone_options else 0
        user_timezone = st.selectbox("What is your timezone?", options=timezone_options, index=default_index)
        
        submitted = st.form_submit_button("Save Profile")
        if submitted and name and phone_number:
            st.session_state.user_profile = {"name": name, "timezone": user_timezone, "phone": phone_number}
            st.rerun()
    st.stop()

# --- GEMINI AI SETUP ---
if st.session_state.chat_session is None:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        add_event_tool = genai.protos.FunctionDeclaration(name="add_event", description="Adds an event to the calendar.", parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={"summary": genai.protos.Schema(type=genai.protos.Type.STRING), "start_time_str": genai.protos.Schema(type=genai.protos.Type.STRING), "end_time_str": genai.protos.Schema(type=genai.protos.Type.STRING), "description": genai.protos.Schema(type=genai.protos.Type.STRING)}, required=["summary", "start_time_str", "end_time_str"]))
        get_events_tool = genai.protos.FunctionDeclaration(name="get_todays_events", description="Gets today's events.")
        tools = genai.protos.Tool(function_declarations=[add_event_tool, get_events_tool])
        
        user_tz_str = st.session_state.user_profile['timezone']
        user_tz = pytz.timezone(user_tz_str)
        current_time = datetime.now(user_tz)
        
        SYSTEM_PROMPT = f"""You are FocusFlow, a calendar assistant for {st.session_state.user_profile['name']}.
        Current date/time: {current_time.strftime('%Y-%m-%d %H:%M')} ({user_tz_str})
        CRITICAL TIMEZONE RULE: 
        - User is in {user_tz_str} timezone.
        - When user says "8 PM today", that means 8 PM in their local time.
        - You MUST create naive time strings for the function call in the format: YYYY-MM-DDTHH:MM:SS
        RULES:
        1. For scheduling: Call add_event with summary, start_time_str, and end_time_str.
        2. For viewing schedule: Call get_todays_events.
        3. If info is missing, ask briefly for only what is needed.
        Examples for TODAY ({current_time.strftime('%Y-%m-%d')}):
        - "8 PM today" should have start_time_str: "{current_time.replace(hour=20, minute=0, second=0).strftime('%Y-%m-%dT%H:%M:%S')}"
        - "2:30 PM today" should have start_time_str: "{current_time.replace(hour=14, minute=30, second=0).strftime('%Y-%m-%dT%H:%M:%S')}"
        """
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[tools], system_instruction=SYSTEM_PROMPT)
        st.session_state.chat_session = model.start_chat(history=[])
    except Exception as e:
        st.error(f"Error setting up AI model: {e}")
        st.exception(e)
        st.stop()

# --- MAIN UI ---
st.title(f"🤖 Hey, {st.session_state.user_profile['name']}! Let's plan your day.")
gamification_utils.display_gamification_dashboard()

# --- AUTHENTICATION FLOW (uses phone number for token path) ---
if st.session_state.calendar_service is None:
    st.info("Please authenticate with Google Calendar to unlock all features.")
    
    # Construct the unique token path using the user's phone number
    phone_number_sanitized = ''.join(filter(str.isdigit, st.session_state.user_profile['phone']))
    user_token_path = f"tokens/token_{phone_number_sanitized}.json"

    if st.button("Login with Google"):
        with st.spinner("Please follow the authentication steps in your browser..."):
            # Use the interactive function that can create the token file
            service = calendar_utils.get_calendar_service_for_streamlit(user_token_path)
            if service:
                st.session_state.calendar_service = service
                st.success("Authentication successful!")
                st.rerun()
            else:
                st.error("Authentication failed. Please try again.")
    st.stop()

# --- CHAT HISTORY DISPLAY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CORE LOGIC ---
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
            
            # Pass the required service and timezone objects to the core functions
            service = st.session_state.calendar_service
            user_tz = st.session_state.user_profile['timezone']
            
            function_map = {
                'add_event': lambda **kwargs: calendar_utils.add_event(service=service, user_timezone_str=user_tz, **kwargs),
                'get_todays_events': lambda: calendar_utils.get_todays_events(service=service, user_timezone_str=user_tz)
            }
            
            tool_response = function_map[tool_name](**args)
            assistant_response = tool_response
            
            if tool_name == "add_event" and assistant_response.strip().startswith("✅"):
                gamification_feedback = gamification_utils.award_xp(gamification_utils.XP_PER_TASK_SCHEDULED, "task")
                assistant_response += f"\n\n*{gamification_feedback}*"
                
        elif part.text:
            assistant_response = part.text
        else:
            assistant_response = "I received an unusual response from the AI. Please try again."
            
    except Exception as e:
        st.error("An unexpected error occurred:")
        st.exception(e)
        assistant_response = "I encountered an error. Please see the details above and try your request again."
    
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

# --- INPUT HANDLING ---
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