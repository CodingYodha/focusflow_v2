# telegram_agent.py
import os
import json
import asyncio
from quart import Quart, request
import telegram
import google.generativeai as genai
import pytz
from datetime import datetime
import toml

from core import calendar_utils, transcriber

# --- ROBUST SECRET LOADING ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not GOOGLE_API_KEY or not TELEGRAM_BOT_TOKEN:
    try:
        secrets = toml.load(os.path.join(".streamlit", "secrets.toml"))
        GOOGLE_API_KEY = secrets.get("GOOGLE_API_KEY")
        TELEGRAM_BOT_TOKEN = secrets.get("TELEGRAM_BOT_TOKEN")
    except FileNotFoundError: raise ValueError("secrets.toml not found.")
if not GOOGLE_API_KEY or not TELEGRAM_BOT_TOKEN: raise ValueError("API keys are missing.")

# --- INITIALIZATION ---
app = Quart(__name__)
genai.configure(api_key=GOOGLE_API_KEY)
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
try:
    with open('telegram_users.json', 'r') as f:
        users_db = json.load(f)
except FileNotFoundError: users_db = {}

# --- EXPLICIT TOOL DEFINITION ---
add_event_tool = genai.protos.FunctionDeclaration(name="add_event", description="Adds an event to the calendar.", parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={"summary": genai.protos.Schema(type=genai.protos.Type.STRING), "start_time_str": genai.protos.Schema(type=genai.protos.Type.STRING), "end_time_str": genai.protos.Schema(type=genai.protos.Type.STRING)}, required=["summary", "start_time_str", "end_time_str"]))
get_events_tool = genai.protos.FunctionDeclaration(name="get_events", description="Fetches events for a specific date.", parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={"date_str": genai.protos.Schema(type=genai.protos.Type.STRING, description="The date in YYYY-MM-DD format. If omitted, today's date will be used.")}))
tools = genai.protos.Tool(function_declarations=[add_event_tool, get_events_tool])

# --- THE MAIN ASYNC TELEGRAM WEBHOOK ---
@app.route(f'/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
async def respond():
    data = await request.get_json(force=True)
    update = telegram.Update.de_json(data, bot)
    if not update.message: return 'ok'
    
    chat_id = str(update.message.chat.id)
    user_profile = users_db.get(chat_id)
    if not user_profile:
        await bot.send_message(chat_id=chat_id, text="Hello! Your Telegram account isn't recognized. Please register in the FocusFlow web app first.")
        return 'ok'

    user_prompt = ""
    if update.message.voice:
        await bot.send_message(chat_id=chat_id, text="🎙️ Got it! Let me listen...")
        file_info = await bot.get_file(update.message.voice.file_id)
        user_prompt = transcriber.transcribe_telegram_voice_note(file_info.file_path)
    elif update.message.text:
        user_prompt = update.message.text
    
    if not user_prompt:
        await bot.send_message(chat_id=chat_id, text="Sorry, I couldn't understand that.")
        return 'ok'
    
    # --- CORE AGENT LOGIC ---
    try:
        service = calendar_utils.get_calendar_service_for_agent(user_profile['google_token_path'])
        if not service: raise Exception("Could not authenticate with Google Calendar.")
        
        user_tz_str = user_profile['timezone']
        SYSTEM_PROMPT = f"You are a function-calling AI model. User's timezone is {user_tz_str}. Current date is {datetime.now(pytz.timezone(user_tz_str)).strftime('%Y-%m-%d')}. Your job is to convert requests into function calls. For scheduling, call `add_event` with timezone-NAIVE time strings (YYYY-MM-DDTHH:MM:SS). For viewing events, call `get_events`, inferring the date_str if the user specifies 'tomorrow' or another date."
        
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", tools=[tools], system_instruction=SYSTEM_PROMPT)
        chat = model.start_chat()

        ai_response = await chat.send_message_async(user_prompt)
        part = ai_response.parts[0]
        
        final_message = ""
        if part.function_call:
            tool_name = part.function_call.name
            args = dict(part.function_call.args)
            
            # --- THE DEFINITIVE FIX ---
            # Correctly pass all necessary context (service, user_timezone_str) to BOTH functions.
            if tool_name == 'add_event':
                # Pass the timezone string with the correct parameter name
                final_message = calendar_utils.add_event(
                    service=service, 
                    user_timezone_str=user_tz_str,  # Correct parameter name
                    **args
                )
            elif tool_name == 'get_events':
                final_message = calendar_utils.get_events(
                    service=service, 
                    user_timezone_str=user_tz_str,  # Correct parameter name
                    **args
                )
            else:
                final_message = "I tried to use a function that doesn't exist."

        elif part.text:
            final_message = part.text
        
        await bot.send_message(chat_id=chat_id, text=final_message or "I'm not sure how to respond to that.")

    except Exception as e:
        if "MALFORMED_FUNCTION_CALL" in str(e):
             await bot.send_message(chat_id=chat_id, text="I'm missing some information. For an event, I need a title, start time, and end time.")
        else:
            print(f"Error processing command: {e}")
            await bot.send_message(chat_id=chat_id, text="Sorry, I encountered an internal error.")

    return 'ok'

@app.route('/set_webhook', methods=['GET'])
async def set_webhook():
    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL")
    if webhook_url:
        webhook_url_with_token = f'{webhook_url}/{TELEGRAM_BOT_TOKEN}'
        await bot.set_webhook(webhook_url_with_token)
        return f"webhook setup ok to {webhook_url_with_token}"
    return "No webhook URL provided."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    try:
        app.run(port=port, debug=True)
    except KeyboardInterrupt: pass