# app.py
import streamlit as st
import google.generativeai as genai
from datetime import datetime
import pytz
import os
import spotipy

# Import from the new 'core' directory
from core import calendar_utils, gamification_utils, audio_utils, spotify_utils

st.set_page_config(page_title="FocusFlow - Main", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

def initialize_app_state():
    """Initializes all required session state variables to prevent errors on first run."""
    if "user_profile" not in st.session_state: st.session_state.user_profile = None
    if "calendar_service" not in st.session_state: st.session_state.calendar_service = None
    if "spotify_client" not in st.session_state: st.session_state.spotify_client = None
    if "messages" not in st.session_state: st.session_state.messages = []
    if "chat_session" not in st.session_state: st.session_state.chat_session = None
    if "voice_input_text" not in st.session_state: st.session_state.voice_input_text = ""
    if "xp" not in st.session_state: gamification_utils.initialize_gamification()

initialize_app_state()

# --- STAGE 1: ONBOARDING ---
# This block runs FIRST and exclusively until a profile is created.
if st.session_state.user_profile is None:
    st.title("Welcome to FocusFlow V2! 🚀")
    st.subheader("Let's create your profile to get started.")
    with st.form("profile_form"):
        name = st.text_input("What's your name?")
        telegram_id = st.text_input("What's your Telegram Chat ID?", help="Required for the Telegram agent. Find this by messaging your bot and checking the /getUpdates URL.")
        timezone_options = pytz.common_timezones
        default_index = timezone_options.index('Asia/Kolkata') if 'Asia/Kolkata' in timezone_options else 0
        user_timezone = st.selectbox("What is your timezone?", options=timezone_options, index=default_index)
        
        submitted = st.form_submit_button("Save Profile")
        if submitted and name and telegram_id:
            st.session_state.user_profile = {"name": name, "timezone": user_timezone, "telegram_id": telegram_id}
            st.rerun() # Rerun to move to the next stage
    st.stop() # Stop the script here until the profile is created

# --- STAGE 2: AUTHENTICATION & MAIN APP (Only runs if a profile exists) ---

# First, handle the Spotify redirect logic if it's present in the URL
query_params = st.query_params
auth_code = query_params.get("code")
if auth_code and not st.session_state.spotify_client:
    auth_manager = spotify_utils.get_spotify_auth_manager()
    if auth_manager:
        with st.spinner("Finalizing Spotify connection..."):
            try:
                auth_manager.get_access_token(auth_code, as_dict=False)
                st.session_state.spotify_client = spotipy.Spotify(auth_manager=auth_manager)
                # Clear the auth code from the URL for a clean user experience
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error("Spotify authentication failed during token exchange."); st.exception(e)

# Display the main hub UI
st.title(f"🤖 Hey, {st.session_state.user_profile['name']}! Let's get you connected.")
st.write("Please connect your accounts below to unlock all of FocusFlow's features.")
gamification_utils.display_gamification_dashboard()
st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("🗓️ Google Calendar")
    if st.session_state.calendar_service:
        st.success("✓ Connected to Google Calendar!")
    else:
        st.info("Connect to enable AI scheduling features.")
        user_token_path = f"tokens/token_{st.session_state.user_profile['telegram_id']}.json"
        if st.button("Login with Google", use_container_width=True):
            with st.spinner("Please follow authentication steps..."):
                service = calendar_utils.get_calendar_service_for_streamlit(user_token_path)
                if service: st.session_state.calendar_service = service; st.rerun()
                else: st.error("Google authentication failed.")
with col2:
    st.subheader("🎵 Spotify")
    if st.session_state.spotify_client:
        st.success("✓ Connected to Spotify!")
    else:
        st.info("Connect to enable music therapy.")
        auth_manager = spotify_utils.get_spotify_auth_manager()
        if auth_manager: st.link_button("Login to Spotify", auth_manager.get_authorize_url(), use_container_width=True)

# Only show the chat interface if BOTH services are connected
if st.session_state.calendar_service and st.session_state.spotify_client:
    st.divider()
    st.header("💬 AI Assistant Ready")
    st.write("All systems are go! You can now use the chat below or navigate to other pages.")
    
    # Setup Gemini session only after auth is complete
    if st.session_state.chat_session is None:
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            add_event_tool = genai.protos.FunctionDeclaration(name="add_event", description="Adds an event to the calendar.", parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={"summary": genai.protos.Schema(type=genai.protos.Type.STRING), "start_time_str": genai.protos.Schema(type=genai.protos.Type.STRING), "end_time_str": genai.protos.Schema(type=genai.protos.Type.STRING), "description": genai.protos.Schema(type=genai.protos.Type.STRING)}, required=["summary", "start_time_str", "end_time_str"]))
            get_events_tool = genai.protos.FunctionDeclaration(name="get_events", description="Fetches events for a specific date.", parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={"date_str": genai.protos.Schema(type=genai.protos.Type.STRING, description="The date in YYYY-MM-DD format. If omitted, today's date will be used.")}))
            tools = genai.protos.Tool(function_declarations=[add_event_tool, get_events_tool])
            user_tz_str = st.session_state.user_profile['timezone']
            user_tz = pytz.timezone(user_tz_str)
            current_time = datetime.now(user_tz)
            SYSTEM_PROMPT = f"""You are FocusFlow, a calendar assistant for {st.session_state.user_profile['name']}. Current date/time: {current_time.strftime('%Y-%m-%d %H:%M')} ({user_tz_str}). CRITICAL TIMEZONE RULE: User is in {user_tz_str} timezone. You MUST create naive time strings in YYYY-MM-DDTHH:MM:SS format. RULES: 1. For scheduling: Call add_event. 2. For viewing: Call get_events. Infer dates like 'tomorrow'. 3. If info is missing, ask briefly for only what is needed."""
            model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[tools], system_instruction=SYSTEM_PROMPT)
            st.session_state.chat_session = model.start_chat(history=[])
        except Exception as e: st.error(f"Error setting up AI model: {e}"); st.exception(e); st.stop()

    # Chat history display
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])

    # Core prompt processing logic
    def process_prompt(user_prompt):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        try:
            with st.spinner("Thinking..."): response = st.session_state.chat_session.send_message(user_prompt)
            if not response.parts: raise ValueError("The AI returned an empty response.")
            part = response.parts[0]
            if part.function_call:
                function_call = part.function_call; tool_name = function_call.name; args = dict(function_call.args)
                service = st.session_state.calendar_service; user_tz = st.session_state.user_profile['timezone']
                function_map = {'add_event': lambda **kwargs: calendar_utils.add_event(service=service, user_timezone_str=user_tz, **kwargs), 'get_events': lambda **kwargs: calendar_utils.get_events(service=service, user_timezone_str=user_tz, **kwargs)}
                with st.spinner(f"Accessing Google Calendar..."): tool_response = function_map[tool_name](**args)
                assistant_response = tool_response
                if tool_name == "add_event" and assistant_response.strip().startswith("✅"):
                    gamification_feedback = gamification_utils.award_xp(gamification_utils.XP_PER_TASK_SCHEDULED, "task")
                    assistant_response += f"\n\n*{gamification_feedback}*"
            elif part.text: assistant_response = part.text
            else: assistant_response = "I received an unusual response from the AI."
        except Exception as e:
            st.error("An unexpected error occurred:"); st.exception(e)
            assistant_response = "I encountered an error. Please try again."
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    # Input handling logic
    if st.session_state.voice_input_text:
        prompt_to_process = st.session_state.voice_input_text; st.session_state.voice_input_text = ""
        process_prompt(prompt_to_process); st.rerun()
    if text_prompt := st.chat_input("Schedule a task or ask about your day"):
        process_prompt(text_prompt); st.rerun()
    st.sidebar.header("Voice Assistant 🎤")
    if st.sidebar.button("Talk to FocusFlow"):
        transcribed_text = audio_utils.transcribe_audio_from_mic()
        if transcribed_text: st.session_state.voice_input_text = transcribed_text; st.rerun()