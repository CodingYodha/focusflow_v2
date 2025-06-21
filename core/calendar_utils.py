# core/calendar_utils.py
import datetime as dt
import os
import pytz
import httplib2

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_httplib2 import AuthorizedHttp

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = "credentials.json"

# --- No changes needed in these authentication functions ---
def _build_service_with_creds(creds):
    if not creds: return None
    try:
        http_client = httplib2.Http(timeout=15)
        authorized_http = AuthorizedHttp(creds, http=http_client)
        service = build('calendar', 'v3', http=authorized_http)
        return service
    except Exception as e:
        print(f"ERROR: Could not build Google Calendar service. {e}")
        return None

def get_calendar_service_for_streamlit(user_token_path):
    creds = None
    if not os.path.exists('tokens'): os.makedirs('tokens')
    if os.path.exists(user_token_path):
        creds = Credentials.from_authorized_user_file(user_token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(user_token_path, 'w') as token:
            token.write(creds.to_json())
    return _build_service_with_creds(creds)

def get_calendar_service_for_agent(user_token_path):
    creds = None
    if os.path.exists(user_token_path):
        creds = Credentials.from_authorized_user_file(user_token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(user_token_path, 'w') as token: token.write(creds.to_json())
            except Exception: return None
        else: return None
    return _build_service_with_creds(creds)


def get_events(service, user_timezone_str, date_str=None):
    """
    Fetches events for a specific date string (YYYY-MM-DD).
    Defaults to the current day if no date is provided.
    """
    if not service: return "Error: Could not connect to Google Calendar."
    try:
        user_tz = pytz.timezone(user_timezone_str)
        
        if date_str:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            day_descriptor = f"for {target_date.strftime('%B %d, %Y')}"
        else:
            target_date = dt.datetime.now(user_tz).date()
            day_descriptor = "for today"

        start_of_day = user_tz.localize(dt.datetime.combine(target_date, dt.time.min))
        end_of_day = user_tz.localize(dt.datetime.combine(target_date, dt.time.max))

        events_result = service.events().list(
            calendarId='primary', 
            timeMin=start_of_day.isoformat(), 
            timeMax=end_of_day.isoformat(),
            singleEvents=True, 
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if not events:
            return f"Your schedule is clear {day_descriptor}! ✨"

        event_list = []
        for event in events:
            # --- THE DEFINITIVE FIX ---
            # Get the datetime string from the Google API
            datetime_str = event['start'].get('dateTime', event['start'].get('date'))
            
            # Make it compatible with older Python versions by replacing 'Z' with '+00:00'
            compatible_datetime_str = datetime_str.replace('Z', '+00:00')
            
            # Now parse the compatible string
            parsed_time = dt.datetime.fromisoformat(compatible_datetime_str)

            event_list.append(
                f"- **{event['summary']}** at {parsed_time.astimezone(user_tz).strftime('%I:%M %p')}"
            )
        
        return f"Here is your schedule {day_descriptor}:\n" + "\n".join(event_list)
    except Exception as e:
        return f"A system error occurred while fetching events: {e}"

# --- FIXED: Changed user_tz_str to user_timezone_str in the conflict check ---
def add_event(service, user_timezone_str, summary, start_time_str, end_time_str, description=None, location=None):
    if not service: return "Error: Could not connect to Google Calendar."
    try:
        user_tz = pytz.timezone(user_timezone_str)
        start_dt_naive = dt.datetime.fromisoformat(start_time_str)
        end_dt_naive = dt.datetime.fromisoformat(end_time_str)
        start_dt_aware = user_tz.localize(start_dt_naive)
        end_dt_aware = user_tz.localize(end_dt_naive)
        conflict = _check_for_conflicts(service, start_dt_aware.isoformat(), end_dt_aware.isoformat(), user_timezone_str)  # FIXED: Changed user_tz_str to user_timezone_str
        if conflict: return f"❌ Conflict detected. {conflict}."
        event_body = {'summary': summary, 'location': location, 'description': description or 'Scheduled by FocusFlow', 'start': {'dateTime': start_dt_aware.isoformat()}, 'end': {'dateTime': end_dt_aware.isoformat()}, 'reminders': {'useDefault': True}}
        created_event = service.events().insert(calendarId='primary', body=event_body).execute()
        return (f"✅ Event '{summary}' was successfully added for {start_dt_aware.strftime('%b %d at %I:%M %p')}.")
    except Exception as e: return f"❌ An unexpected error occurred: {e}"

def _check_for_conflicts(service, start_time_iso, end_time_iso, user_timezone_str):  # FIXED: Changed user_tz_str to user_timezone_str
    if not service: return "Authentication service not available"
    try:
        events = service.events().list(calendarId='primary', timeMin=start_time_iso, timeMax=end_time_iso, timeZone=user_timezone_str, singleEvents=True).execute().get('items', [])  # FIXED: Changed user_tz_str to user_timezone_str
        return f"You already have '{events[0]['summary']}' scheduled" if events else None
    except Exception: return "Could not check for conflicts."