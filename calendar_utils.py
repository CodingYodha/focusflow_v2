# calendar_utils.py
import datetime as dt
import os.path
import streamlit as st
from datetime import timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = "credentials.json"

@st.cache_resource
def authenticate_google_calendar():
    # Authentication logic remains the same...
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
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        st.error(f"An error occurred: {error}")
        return None

def check_for_conflicts(start_time, end_time):
    """Checks if there are any events in the given time slot."""
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True
    ).execute()
    
    conflicts = events_result.get('items', [])
    if not conflicts:
        return "No conflicts found."
    else:
        conflict_names = [event['summary'] for event in conflicts]
        return f"Conflict found: You already have '{', '.join(conflict_names)}' scheduled at this time."

def get_todays_events():
    """Fetches all events scheduled for the current day."""
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."

    now = dt.datetime.now(timezone.utc)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    time_max = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
    
    events = service.events().list(
        calendarId='primary', timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy='startTime'
    ).execute().get('items', [])

    if not events:
        return "Your schedule for today is clear! A perfect day to get things done."
    
    event_list = []
    for event in events:
        start_raw = event["start"].get("dateTime", event["start"].get("date"))
        end_raw = event["end"].get("dateTime", event["end"].get("date"))
        
        try:
            start_dt = dt.datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            end_dt = dt.datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
        except ValueError:
            time_str = "All day"
        
        event_list.append(f"- **{event['summary']}** ({time_str})")
        
    return "Here is your schedule for today:\n" + "\n".join(event_list)

def add_event(summary, start_time, end_time, description=None, location=None):
    """Adds a new event to the calendar."""
    service = st.session_state.get("calendar_service")
    if not service: return "Error: Not authenticated."
        
    user_tz = st.session_state.get('user_profile', {}).get('timezone', 'America/New_York')
    event = {
        'summary': summary, 'location': location,
        'description': description or 'Scheduled by FocusFlow V2',
        'start': {'dateTime': start_time, 'timeZone': user_tz},
        'end': {'dateTime': end_time, 'timeZone': user_tz},
        'reminders': {'useDefault': True},
    }
    
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    st.session_state.tasks_completed += 1 # Increment task counter
    return f"Event '{summary}' was successfully added to your calendar."