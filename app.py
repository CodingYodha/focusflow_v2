# app.py
import streamlit as st
import google.generativeai as genai
from datetime import datetime

# Import our utility modules
import calendar_utils
import gamification
import audio_utils

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="FocusFlow V2", page_icon="🤖",
    layout="wide", initial_sidebar_state="expanded",
)

# --- GEMINI AND API SETUP ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        tools=[calendar_utils.add_event, calendar_utils.list_upcoming_events]
    )
    SYSTEM_PROMPT = """
    You are FocusFlow, a friendly and encouraging AI productivity coach...
    (The rest of your system prompt is fine, no changes needed here)
    """
    chat = model.start_chat(enable_automatic_function_calling=True)
except Exception as e:
    st.error(f"Error setting up AI model: {e}")
    st.stop()
    
# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state: st.session_state.messages = []
if "chat_session" not in st.session_state: st.session_state.chat_session = chat
if "calendar_service" not in st.session_state: st.session_state.calendar_service = None
if "xp" not in st.session_state: st.session_state.xp = 0
if "level" not in st.session_state: st.session_state.level = 1
if "tasks_completed" not in st.session_state: st.session_state.tasks_completed = 0
if "streak" not in st.session_state: st.session_state.streak = 0
if "badges" not in st.session_state: st.session_state.badges = []
if "auto_play_audio" not in st.session_state: st.session_state.auto_play_audio = None

# --- AUTHENTICATION AND UI SETUP ---
st.title("🤖 FocusFlow V2")
st.caption("Your AI-Powered Productivity Coach")

if st.session_state.calendar_service is None:
    st.info("Please authenticate with your Google Calendar to begin.")
    if st.button("Login with Google"):
        with st.spinner("Authenticating..."):
            service = calendar_utils.authenticate_google_calendar()
            if service:
                st.session_state.calendar_service = service
                st.success("Authentication successful! Let's get productive. 💪")
                welcome_message = "Hello! I'm FocusFlow. What's our first goal today?"
                st.session_state.messages.append({"role": "assistant", "content": welcome_message})
                st.rerun()
            else:
                st.error("Authentication failed.")
    st.stop()

gamification.display_gamification_dashboard()

# --- CHAT HISTORY DISPLAY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.auto_play_audio:
    audio_utils.text_to_speech_autoplay(st.session_state.auto_play_audio)
    st.session_state.auto_play_audio = None

# --- PROMPT PROCESSING LOGIC ---
prompt = None
# FIX 1: Prioritize voice input if it exists in session state
if "voice_input" in st.session_state and st.session_state.voice_input:
    prompt = st.session_state.voice_input
    st.session_state.voice_input = "" # Clear it after use
else:
    # Otherwise, get input from the text chat box
    prompt = st.chat_input("What would you like to do?")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Thinking... 🤔"):
        # FIX 2: No longer need to inject the service object
        full_prompt = SYSTEM_PROMPT.format(current_date=datetime.now().strftime("%Y-%m-%d")) + "\nUser: " + prompt
        response = st.session_state.chat_session.send_message(full_prompt)

    assistant_response = response.text
    
    # Check if a function call happened to award points
    function_called = any(part.function_call for part in response.parts if hasattr(part, 'function_call'))
    if function_called:
        # Check if the specific function was 'add_event'
        add_event_called = any(part.function_call.name == "add_event" for part in response.parts if hasattr(part, 'function_call'))
        if add_event_called:
            gamification_feedback = gamification.update_gamification_stats()
            assistant_response += f"\n\n*{gamification_feedback}*"

    with st.chat_message("assistant"):
        st.markdown(assistant_response)
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
    
    st.session_state.auto_play_audio = assistant_response
    st.rerun()

# --- VOICE INPUT WIDGET ---
st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    transcribed_text = audio_utils.transcribe_audio_from_mic()
    if transcribed_text:
        # Instead of trying to fill a widget, we put it in session state and rerun
        st.session_state.voice_input = transcribed_text
        st.rerun()