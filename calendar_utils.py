# calendar_utils.py
import datetime as dt
import os.path
import streamlit as st
import pytz # Import pytz for robust timezone handling

# Imports for Google API...
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httplib2
from google_auth_httplib2 import AuthorizedHttp 

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = "credentials.json"

@st.cache_resource
def authenticate_google_calendar():
    # This function is correct from the previous fix.
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
        return None

# --- FIX: REWRITTEN add_event TO HANDLE TIMEZONES IN PYTHON ---
def add_event(summary, start_time_str, end_time_str, description=None, location=None):
    """
    Adds an event using the user's local timezone.
    Receives timezone-naive time strings from the AI and makes them timezone-aware here.
    """
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."

    # Get user's timezone from their profile, default to UTC if not found.
    user_tz_str = st.session_state.get('user_profile', {}).get('timezone', 'UTC')
    try:
        user_timezone = pytz.timezone(user_tz_str)
    except pytz.UnknownTimeZoneError:
        return f"❌ Error: The timezone '{user_tz_str}' in your profile is invalid."

    try:
        # Convert the naive time strings from the AI into timezone-AWARE datetime objects.
        start_naive = dt.datetime.fromisoformat(start_time_str)
        end_naive = dt.datetime.fromisoformat(end_time_str)
        
        start_aware = user_timezone.localize(start_naive)
        end_aware = user_timezone.localize(end_naive)

        # Internally check for conflicts using the full, timezone-aware timestamps.
        conflict = check_for_conflicts(start_aware.isoformat(), end_aware.isoformat())
        if conflict:
            return f"❌ Conflict detected. {conflict}."

        # Create the event body, providing both the timestamp AND the timezone.
        # This is the most explicit and reliable way to communicate with the API.
        event = {
            'summary': summary,
            'location': location,
            'description': description or 'Scheduled by FocusFlow V2',
            'start': {
                'dateTime': start_aware.isoformat(),
                'timeZone': user_tz_str,
            },
            'end': {
                'dateTime': end_aware.isoformat(),
                'timeZone': user_tz_str,
            },
            'reminders': {'useDefault': True},
        }
        
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return f"✅ Event '{summary}' was successfully added to your calendar."
    
    except ValueError:
        return "❌ Failed to create event. The date/time format provided was incorrect."
    except HttpError as error:
        return f"❌ Failed to create event. Google Calendar API Error: {error}."
    except Exception as e:
        return f"❌ An unexpected error occurred: {e}"

# Other functions (get_todays_events, check_for_conflicts) remain the same.
def get_todays_events():
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."
    try:
        # Using pytz to get the user's timezone correctly
        user_tz_str = st.session_state.get('user_profile', {}).get('timezone', 'UTC')
        user_tz = pytz.timezone(user_tz_str)
        now = dt.datetime.now(user_tz)
        
        time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        time_max = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
        
        events = service.events().list(calendarId='primary', timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy='startTime').execute().get('items', [])
        if not events:
            return "No events found for today."
        event_list = [f"- **{event['summary']}** ({dt.datetime.fromisoformat(event['start'].get('dateTime')).astimezone(user_tz).strftime('%I:%M %p')})" for event in events]
        return "Here is your schedule for today:\n" + "\n".join(event_list)
    except Exception as e:
        return f"A system error occurred while fetching events: {e}"

def check_for_conflicts(start_time_iso, end_time_iso):
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."
    events = service.events().list(calendarId='primary', timeMin=start_time_iso, timeMax=end_time_iso, singleEvents=True).execute().get('items', [])
    return f"You already have '{events[0]['summary']}' scheduled." if events else None