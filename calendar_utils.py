# calendar_utils.py
# (Imports and authenticate_google_calendar function remain the same as your last working version)
import datetime as dt
import os.path
import streamlit as st
from datetime import timezone
import httplib2
from google_auth_httplib2 import AuthorizedHttp 
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = "credentials.json"

@st.cache_resource
def authenticate_google_calendar():
    # ... This function is correct from the previous fix, no changes needed.
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    try:
        http_client = httplib2.Http(timeout=15)
        authorized_http = AuthorizedHttp(creds, http=http_client)
        service = build('calendar', 'v3', http=authorized_http)
        return service
    except Exception as e:
        st.error(f"A general error occurred during authentication: {e}")
        return None

def get_todays_events():
    """Fetches all events scheduled for the current day."""
    # This function is also likely correct, but we add more error catching.
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."
    try:
        # Get user's timezone
        user_tz_str = st.session_state.get('user_profile', {}).get('timezone', 'UTC')
        user_tz = pytz.timezone(user_tz_str)
        
        # Get today's date in user's timezone
        now_user_tz = dt.datetime.now(user_tz)
        start_of_day = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now_user_tz.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Convert to UTC for API call
        time_min = start_of_day.astimezone(timezone.utc).isoformat()
        time_max = end_of_day.astimezone(timezone.utc).isoformat()
        
        events = service.events().list(calendarId='primary', timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy='startTime').execute().get('items', [])
        if not events:
            return "No events found for today."
        event_list = [f"- **{event['summary']}** ({dt.datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')).replace('Z', '+00:00')).astimezone(user_tz).strftime('%I:%M %p')})" for event in events]
        return "Here is your schedule for today:\n" + "\n".join(event_list)
    except Exception as e:
        return f"A system error occurred while fetching events: {e}"

def check_for_conflicts(start_time, end_time):
    """Helper function to check for conflicts. Not exposed to AI."""
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."
    events = service.events().list(calendarId='primary', timeMin=start_time, timeMax=end_time, singleEvents=True).execute().get('items', [])
    if not events:
        return None
    else:
        return f"You already have '{events[0]['summary']}' scheduled at this time."

# --- FIX: PROPER TIMEZONE HANDLING IN add_event FUNCTION ---
def add_event(summary, start_time, end_time, description=None, location=None):
    """
    Adds an event after checking for conflicts. This is the only scheduling function
    the AI should call.
    """
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."

    try:
        # Get user's timezone
        user_tz_str = st.session_state.get('user_profile', {}).get('timezone', 'UTC')
        user_tz = pytz.timezone(user_tz_str)
        
        # Parse the input times and ensure they're in the user's timezone
        try:
            # Parse the datetime strings
            start_dt = dt.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = dt.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # If the times are in UTC, convert them to user's timezone
            if start_dt.tzinfo == timezone.utc:
                start_dt = start_dt.astimezone(user_tz)
                end_dt = end_dt.astimezone(user_tz)
            elif start_dt.tzinfo is None:
                # If naive datetime, assume it's in user's timezone
                start_dt = user_tz.localize(start_dt)
                end_dt = user_tz.localize(end_dt)
            
            # Convert back to ISO format with proper timezone
            start_time_corrected = start_dt.isoformat()
            end_time_corrected = end_dt.isoformat()
            
        except Exception as parse_error:
            return f"❌ Error parsing time format: {parse_error}. Please use ISO format with timezone."

        # Step 1: Internally check for conflicts before doing anything.
        conflict = check_for_conflicts(start_time_corrected, end_time_corrected)
        if conflict:
            # If a conflict exists, stop and return the conflict message.
            return f"❌ Conflict detected. {conflict}. Please ask the user if they want to schedule it anyway or choose a different time."

        # Step 2: If no conflict, proceed to create the event.
        event = {
            'summary': summary, 
            'location': location,
            'description': description or 'Scheduled by FocusFlow V2',
            'start': {'dateTime': start_time_corrected, 'timeZone': user_tz_str},
            'end': {'dateTime': end_time_corrected, 'timeZone': user_tz_str},
            'reminders': {'useDefault': True},
        }
        
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        # The success message MUST start with this emoji for the gamification to work.
        return f"✅ Event '{summary}' was successfully added to your calendar for {start_dt.strftime('%I:%M %p')} to {end_dt.strftime('%I:%M %p')} ({user_tz_str})."
    
    except HttpError as error:
        return f"❌ Failed to create event. Google Calendar API Error: {error}. The timestamp format might be wrong."
    except Exception as e:
        return f"❌ An unexpected error occurred during event creation: {e}"