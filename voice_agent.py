# voice_agent.py
import os
import json
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import google.generativeai as genai
import pytz
from datetime import datetime

# Import your existing calendar utility functions
import calendar_utils

# --- INITIALIZATION ---
app = Flask(__name__)

# Load secrets (assuming this script is run from the same directory as .streamlit)
# In production, use environment variables.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_FALLBACK_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_FALLBACK_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_FALLBACK_TOKEN")

genai.configure(api_key=GOOGLE_API_KEY)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Load user database
with open('users.json', 'r') as f:
    users_db = json.load(f)

# --- WEBHOOK 1: WHEN A CALL FIRST COMES IN ---
@app.route("/voice", methods=['GET', 'POST'])
def voice():
    """Responds to an incoming call from Twilio."""
    response = VoiceResponse()
    
    caller_number = request.values.get('From')
    user_profile = users_db.get(caller_number)

    if not user_profile:
        response.say("Hello. This phone number is not recognized by FocusFlow. Please register in the web app.", voice='alice')
        return str(response)

    # Greet the user and start listening for their command
    response.say(f"Hello {user_profile['name']}, you've reached FocusFlow. How can I help you schedule your day?", voice='alice')
    
    # Gather speech input and send it to the /process-command webhook
    response.gather(input='speech', action='/process-command', speech_timeout='auto')

    return str(response)

# --- WEBHOOK 2: AFTER THE USER HAS SPOKEN ---
@app.route("/process-command", methods=['GET', 'POST'])
def process_command():
    """Processes the transcribed speech from the user."""
    response = VoiceResponse()
    
    caller_number = request.values.get('From')
    user_profile = users_db.get(caller_number)

    if not user_profile:
        response.say("Sorry, an error occurred identifying you.", voice='alice')
        return str(response)

    # Get the transcribed text
    user_prompt = request.values.get('SpeechResult')

    if not user_prompt:
        response.say("Sorry, I didn't catch that. Please call again.", voice='alice')
        return str(response)
        
    # --- CORE AGENT LOGIC ---
    try:
        # 1. Authenticate Google Calendar for THIS specific user
        service = calendar_utils.authenticate_google_calendar(user_profile['google_token_path'])
        if not service:
            raise Exception("Could not authenticate with Google Calendar. Please re-authorize in the web app.")

        # 2. Set up the Gemini model with the user-specific prompt
        user_tz_str = user_profile['timezone']
        user_tz = pytz.timezone(user_tz_str)
        tz_offset = datetime.now(user_tz).strftime('%z')
        tz_offset_formatted = f"{tz_offset[:-2]}:{tz_offset[-2:]}"

        SYSTEM_PROMPT = f"""
        You are an expert function-calling AI model.
        The user's timezone is `{user_tz_str}`. The current date is {datetime.now().strftime('%Y-%m-%d')}.
        Your ONLY job is to convert the user's speech into a function call.
        For scheduling, call `add_event` with timezone-NAIVE time strings (YYYY-MM-DDTHH:MM:SS).
        For viewing, call `get_todays_events`.
        """
        tools = [calendar_utils.add_event, calendar_utils.get_todays_events] # Assume these are adapted
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=tools, system_instruction=SYSTEM_PROMPT)
        chat = model.start_chat()

        # 3. Call Gemini and process the function call
        ai_response = chat.send_message(user_prompt)
        part = ai_response.parts[0]
        
        if part.function_call:
            tool_name = part.function_call.name
            args = dict(part.function_call.args)
            
            # Re-create the function map, but pass the service object now
            if tool_name == 'add_event':
                tool_response = calendar_utils.add_event(service=service, **args)
            elif tool_name == 'get_todays_events':
                tool_response = calendar_utils.get_todays_events(service=service)
            else:
                tool_response = "Unknown command."

            # 4. Respond to the user over the phone
            final_message = tool_response.replace("✅", "Success.") # Make it sound more natural
            response.say(final_message, voice='alice')
        else:
            response.say(part.text, voice='alice')

    except Exception as e:
        print(f"Error processing command: {e}")
        response.say("Sorry, I encountered an internal error and could not complete your request.", voice='alice')

    response.hangup()
    return str(response)

if __name__ == "__main__":
    app.run(debug=True, port=5001)