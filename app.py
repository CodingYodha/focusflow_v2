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
    gamification.initialize_gamification()

initialize_app_state()

if st.session_state.user_profile is None:
    st.title("Welcome to FocusFlow V2! 🚀")
    # ... Onboarding logic is correct, no changes ...
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
        
        # We only expose the functions the AI should directly call.
        # check_for_conflicts is now an internal helper function.
        tools = [calendar_utils.add_event, calendar_utils.get_todays_events]

        # --- FIX 2: SIMPLIFIED AND MORE DIRECT SYSTEM PROMPT ---
        user_tz_str = st.session_state.user_profile['timezone']
        user_tz = pytz.timezone(user_tz_str)
        tz_offset = datetime.now(user_tz).strftime('%z')
        tz_offset_formatted = f"{tz_offset[:-2]}:{tz_offset[-2:]}"

        SYSTEM_PROMPT = f"""
        You are FocusFlow, an expert AI productivity coach for {st.session_state.user_profile['name']}.
        Your user's timezone is {user_tz_str}. The current date is {datetime.now().strftime('%Y-%m-%d')}.

        **YOUR PRIMARY RULES:**
        1.  **SCHEDULING**: When a user asks to schedule an event (e.g., "schedule study time tomorrow from 2pm to 4pm"), your ONLY task is to call the `add_event` function.
            - You MUST calculate the `start_time` and `end_time` yourself.
            - The format MUST be full ISO 8601 with the user's timezone offset: `YYYY-MM-DDTHH:MM:SS{tz_offset_formatted}`.
            - **DO NOT ask clarifying questions about date, time, or format.** Calculate it from the context and call the function.
        
        2.  **VIEWING SCHEDULE**: When a user asks about their schedule ("what's my schedule?", "am I busy today?"), your ONLY task is to call the `get_todays_events` function.

        3.  **PERSONALITY**: Always be friendly, encouraging, and use emojis.
        """
        
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=tools, system_instruction=SYSTEM_PROMPT)
        st.session_state.chat_session = model.start_chat(history=[])
    except Exception as e:
        st.error(f"Error setting up AI model: {e}")
        st.exception(e)
        st.stop()

st.title(f"🤖 Hey, {st.session_state.user_profile['name']}! Let's plan your day.")
gamification.display_gamification_dashboard()

if st.session_state.calendar_service is None:
    st.info("Please authenticate with Google Calendar to unlock scheduling features.")
    # ... Authentication logic is correct, no changes ...
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
    with st.chat_message("user"):
        st.markdown(user_prompt)

    try:
        with st.spinner("Thinking..."):
            response = st.session_state.chat_session.send_message(user_prompt)
            
            # --- FIX 3: ROBUST CHECK FOR AI RESPONSE ---
            if not response.parts:
                raise ValueError("The AI returned an empty response. It might be a content safety issue or a network problem.")
            
            part = response.parts[0]

            if part.function_call:
                function_call = part.function_call
                tool_name = function_call.name
                args = dict(function_call.args)
                
                function_map = {'add_event': calendar_utils.add_event, 'get_todays_events': calendar_utils.get_todays_events}
                
                with st.spinner(f"Accessing Google Calendar to {tool_name.replace('_', ' ')}..."):
                    tool_response = function_map[tool_name](**args)

                with st.spinner("Summarizing..."):
                    response = st.session_state.chat_session.send_message(
                        genai.Part(function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": str(tool_response)}
                        ))
                    )
                assistant_response = response.text
                
                # --- FIX 4: PRECISE GAMIFICATION TRIGGER ---
                if tool_name == "add_event" and str(tool_response).startswith("✅"):
                    gamification_feedback = gamification.award_xp(gamification.XP_PER_TASK_SCHEDULED, "task")
                    assistant_response += f"\n\n*{gamification_feedback}*"
            else:
                assistant_response = part.text

    except Exception as e:
        st.error("An error occurred. See details below.")
        st.exception(e)
        assistant_response = "I ran into a problem and couldn't complete your request. Please try rephrasing."
    
    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
    
# --- Input Handling & Rerun ---
st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    transcribed_text = audio_utils.transcribe_audio_from_mic()
    if transcribed_text:
        process_prompt(transcribed_text)
        st.rerun()

if text_prompt := st.chat_input("Schedule a task, ask about your day, or just say hi!"):
    process_prompt(text_prompt)
    st.rerun()