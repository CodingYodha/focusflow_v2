# app.py
import streamlit as st
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration
from datetime import datetime
import datetime as dt # For timezone calculations
import json
import pytz

import calendar_utils
import gamification
import audio_utils

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="FocusFlow - Chat", page_icon="🤖",
    layout="wide", initial_sidebar_state="expanded"
)

# --- ROBUST SESSION STATE INITIALIZATION ---
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

# --- ONBOARDING ---
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
            st.success(f"Great to meet you, {name}!")
            st.rerun()
    st.stop()

# --- GEMINI SETUP ---
if st.session_state.chat_session is None:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        tools = [calendar_utils.add_event, calendar_utils.get_todays_events, calendar_utils.check_for_conflicts]

        # --- FIX 1: IMPROVED TIMEZONE HANDLING ---
        user_tz = st.session_state.user_profile['timezone']
        # Get proper timezone offset using pytz
        try:
            tz = pytz.timezone(user_tz)
            now_in_tz = datetime.now(tz)
            tz_offset = now_in_tz.strftime('%z')
            # Insert colon for ISO 8601 format
            tz_offset_formatted = f"{tz_offset[:-2]}:{tz_offset[-2:]}"
        except Exception as e:
            st.error(f"Timezone error: {e}")
            # Fallback to UTC
            tz_offset_formatted = "+00:00"

        SYSTEM_PROMPT = f"""
        You are FocusFlow, an expert AI productivity coach for {st.session_state.user_profile['name']}.
        Your user's timezone is {user_tz}. The current date is {datetime.now().strftime('%Y-%m-%d')}.

        **CRITICAL INSTRUCTION FOR SCHEDULING:**
        When you call the `add_event` function, the `start_time` and `end_time` parameters MUST be in the full ISO 8601 format including the timezone offset.
        - **Correct Format**: `YYYY-MM-DDTHH:MM:SS-HH:MM` or `YYYY-MM-DDTHH:MM:SS+HH:MM`
        - **Example**: For 3 PM today in a timezone 4 hours behind UTC, the format is `2024-08-04T15:00:00-04:00`.
        - The current user's timezone offset is `{tz_offset_formatted}`. You MUST use this offset in your calculations.
        - **You are responsible for calculating this full timestamp. DO NOT ask the user for it.** Convert all natural language times (e.g., "3pm tomorrow", "next Tuesday at noon") into this exact format.

        **Conflict Resolution Workflow:**
        - Step 1: Calculate the full ISO 8601 start and end times based on the user's request.
        - Step 2: ALWAYS call `check_for_conflicts` with these exact timestamps.
        - Step 3: If a conflict exists, inform the user and ask how to proceed.
        - Step 4: Only call `add_event` if there are no conflicts or the user confirms to schedule anyway.

        **Other Capabilities:**
        - To check the schedule, use `get_todays_events`.
        - Maintain a friendly, encouraging, emoji-filled personality.
        """
        
        # Pass the prompt as a system_instruction when creating the model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            tools=tools,
            system_instruction=SYSTEM_PROMPT
        )
        
        st.session_state.chat_session = model.start_chat(history=[])
    except Exception as e:
        st.error(f"Error setting up AI model: {e}")
        st.stop()

# --- UI SETUP ---
st.title(f"🤖 Hey, {st.session_state.user_profile['name']}! Let's plan your day.")
gamification.display_gamification_dashboard()

if st.session_state.calendar_service is None:
    st.info("Please authenticate with Google Calendar to unlock scheduling features.")
    if st.button("Login with Google"):
        with st.spinner("Authenticating..."):
            try:
                st.session_state.calendar_service = calendar_utils.authenticate_google_calendar()
                if st.session_state.calendar_service:
                    st.success("Successfully authenticated with Google Calendar!")
                    st.rerun()
                else:
                    st.error("Failed to authenticate with Google Calendar.")
            except Exception as e:
                st.error(f"Authentication error: {e}")
    st.stop()

# --- CHAT DISPLAY & PROCESSING ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def process_prompt(user_prompt):
    """Process user input and handle AI responses with proper error handling"""
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        try:
            # Add timeout for AI response
            import time
            start_time = time.time()
            timeout = 30  # 30 seconds timeout
            
            # Send initial message to the AI
            response = st.session_state.chat_session.send_message(user_prompt)
            
            # --- FIX: IMPROVED FUNCTION CALLING WITH TIMEOUT ---
            # Check if the AI wants to call a function
            if (response.candidates and 
                len(response.candidates) > 0 and 
                response.candidates[0].content.parts and 
                len(response.candidates[0].content.parts) > 0):
                
                first_part = response.candidates[0].content.parts[0]
                
                # Check if it's a function call
                if hasattr(first_part, 'function_call') and first_part.function_call:
                    function_call = first_part.function_call
                    tool_name = function_call.name
                    args = dict(function_call.args)
                    
                    response_placeholder.markdown(f"🔄 Calling {tool_name.replace('_', ' ')}...")
                    
                    # Map function names to actual functions
                    function_map = {
                        'add_event': calendar_utils.add_event,
                        'get_todays_events': calendar_utils.get_todays_events,
                        'check_for_conflicts': calendar_utils.check_for_conflicts
                    }
                    
                    if tool_name in function_map:
                        try:
                            # Call the function with timeout protection
                            if time.time() - start_time > timeout:
                                raise TimeoutError("Function call timed out")
                                
                            response_placeholder.markdown(f"⚙️ Executing {tool_name.replace('_', ' ')}...")
                            tool_response = function_map[tool_name](**args)
                            
                            response_placeholder.markdown("🤔 Processing results...")
                            
                            # --- FIXED FUNCTION RESPONSE HANDLING ---
                            # Use the correct way to send function responses
                            try:
                                # Method 1: Try the newer API structure
                                function_response = {
                                    "function_call": {
                                        "name": tool_name,
                                        "response": {"result": str(tool_response)}
                                    }
                                }
                                
                                final_response = st.session_state.chat_session.send_message(
                                    f"Function {tool_name} returned: {str(tool_response)}"
                                )
                                
                                if final_response and final_response.text:
                                    assistant_response = final_response.text
                                else:
                                    raise Exception("No AI response received")
                                    
                            except Exception as ai_error:
                                # Fallback: Format the response manually
                                if tool_name == "get_todays_events":
                                    if "No events" in str(tool_response) or not tool_response or str(tool_response).strip() == "":
                                        assistant_response = "📅 Good news! You have no events scheduled for today. It's a free day for you to focus on whatever you'd like! ✨"
                                    else:
                                        assistant_response = f"📅 Here's your schedule for today, {datetime.now().strftime('%B %d, %Y')}:\n\n{tool_response}"
                                elif tool_name == "add_event":
                                    assistant_response = f"✅ Event scheduling result: {tool_response}"
                                elif tool_name == "check_for_conflicts":
                                    assistant_response = f"🔍 Conflict check result: {tool_response}"
                                else:
                                    assistant_response = f"✅ {tool_name.replace('_', ' ').title()} completed: {tool_response}"
                            
                            # Award points for successful task scheduling
                            if tool_name == "add_event" and ("successfully" in str(tool_response).lower() or "added" in str(tool_response).lower()):
                                gamification_feedback = gamification.award_xp(gamification.XP_PER_TASK_SCHEDULED, "task")
                                assistant_response += f"\n\n*{gamification_feedback}*"
                                
                        except TimeoutError:
                            assistant_response = f"The {tool_name.replace('_', ' ')} operation is taking too long. Please try again."
                        except Exception as func_error:
                            # Handle function execution errors gracefully
                            st.error(f"Error executing {tool_name}: {str(func_error)}")
                            assistant_response = f"I encountered an issue while trying to {tool_name.replace('_', ' ')}: {str(func_error)}"
                    else:
                        assistant_response = f"I tried to use an unknown function: {tool_name}. Please try rephrasing your request."
                
                # Handle regular text responses
                elif hasattr(first_part, 'text') and first_part.text:
                    assistant_response = first_part.text
                else:
                    assistant_response = "I'm not sure how to respond to that. Could you please rephrase your request?"
            
            # --- HANDLE EMPTY OR MALFORMED RESPONSES ---
            else:
                assistant_response = "I'm having trouble understanding your request. Could you please try again?"

        except Exception as e:
            # --- COMPREHENSIVE ERROR HANDLING ---
            st.error(f"An error occurred: {str(e)}")
            assistant_response = "I'm experiencing some technical difficulties. Please try again in a moment."

        # Display the final response
        response_placeholder.markdown(assistant_response)
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

# --- INPUT HANDLING ---
st.sidebar.header("Voice Assistant 🎤")
if st.sidebar.button("Talk to FocusFlow"):
    try:
        transcribed_text = audio_utils.transcribe_audio_from_mic()
        if transcribed_text:
            process_prompt(transcribed_text)
        else:
            st.sidebar.warning("No audio detected. Please try again.")
    except Exception as e:
        st.sidebar.error(f"Voice recognition error: {e}")

if text_prompt := st.chat_input("Schedule a task, ask about your day, or just say hi!"):
    process_prompt(text_prompt)