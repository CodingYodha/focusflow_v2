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
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                st.error(f"Error refreshing token: {e}. Deleting token and re-authenticating.")
                if os.path.exists("token.json"):
                    os.remove("token.json")
                creds = None
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        st.error(f"An error occurred with Google Calendar API: {error}")
        return None

def list_upcoming_events(max_results=10):
    """Lists upcoming events. It gets the service object from session_state."""
    # --- FIX: Get service from session state, don't accept as argument ---
    service = st.session_state.get("calendar_service")
    if not service:
        return "Error: Google Calendar service is not available. Please authenticate."

    try:
        now = dt.datetime.now(timezone.utc).isoformat()
        
        events_result = service.events().list(
            calendarId="primary", timeMin=now, maxResults=max_results,
            singleEvents=True, orderBy="startTime"
        ).execute()
        
        events = events_result.get("items", [])

        if not events:
            return "No upcoming events found. Your schedule is clear! ✨"
        
        event_list = []
        for event in events:
            start_raw = event["start"].get("dateTime", event["start"].get("date"))
            try:
                start_dt = dt.datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                start_formatted = start_dt.strftime("%a, %b %d at %I:%M %p")
            except ValueError:
                 start_formatted = start_raw
            
            event_list.append(f"- **{event['summary']}** on {start_formatted}")
            
        return "Here are your upcoming events:\n" + "\n".join(event_list)
    except HttpError as error:
        return f"An error occurred while listing events: {error}"

def add_event(summary, start_time, end_time, location=None, description=None, timezone="America/New_York"):
    """Adds an event. It gets the service object from session_state."""
    # --- FIX: Get service from session state, don't accept as argument ---
    service = st.session_state.get("calendar_service")
    if not service:
        return "Error: Google Calendar service is not available. Please authenticate."
        
    try:
        event = {
            "summary": summary, "location": location,
            "description": description or 'Scheduled by FocusFlow V2',
            "start": {"dateTime": start_time, "timeZone": timezone},
            "end": {"dateTime": end_time, "timeZone": timezone},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]}
        }
        created_event = service.events().insert(calendarId="primary", body=event).execute()
        return f"✅ Event created successfully! You can view it here: {created_event.get('htmlLink')}"
    except HttpError as error:
        return f"❌ An error occurred while creating the event: {error}"