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

def _build_service_with_creds(creds):
    """Internal helper function to build the service object from credentials."""
    if not creds:
        return None
    try:
        http_client = httplib2.Http(timeout=15)
        authorized_http = AuthorizedHttp(creds, http=http_client)
        service = build('calendar', 'v3', http=authorized_http)
        return service
    except Exception as e:
        print(f"ERROR: Could not build Google Calendar service. {e}")
        return None

def get_calendar_service_for_streamlit(user_token_path):
    """
    Handles authentication for the INTERACTIVE Streamlit app.
    It can create a new token file if one doesn't exist by opening a browser.
    """
    creds = None
    # Ensure the 'tokens' directory exists
    if not os.path.exists('tokens'):
        os.makedirs('tokens')
        
    if os.path.exists(user_token_path):
        creds = Credentials.from_authorized_user_file(user_token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # This is the interactive flow that opens a browser for the user to consent.
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the new or refreshed credentials to the user's specific path
        with open(user_token_path, 'w') as token:
            token.write(creds.to_json())
            
    return _build_service_with_creds(creds)

def get_calendar_service_for_agent(user_token_path):
    """
    Handles authentication for the NON-INTERACTIVE Voice Agent.
    It relies on a pre-existing, valid token and can refresh it, but CANNOT create a new one.
    """
    creds = None
    if os.path.exists(user_token_path):
        creds = Credentials.from_authorized_user_file(user_token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(user_token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception:
                return None # Refresh failed, agent cannot proceed.
        else:
            return None # No valid token, agent cannot proceed.
            
    return _build_service_with_creds(creds)

def get_todays_events(service, user_timezone_str):
    """
    Fetches events for the user's current day in their local timezone.
    """
    if not service: return "Error: Could not connect to Google Calendar."
    try:
        user_tz = pytz.timezone(user_timezone_str)
        now_user_tz = dt.datetime.now(user_tz)
        
        start_of_day = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now_user_tz.replace(hour=23, minute=59, second=59, microsecond=999999)

        events_result = service.events().list(
            calendarId='primary', 
            timeMin=start_of_day.isoformat(), 
            timeMax=end_of_day.isoformat(),
            timeZone=user_tz_str,
            singleEvents=True, 
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        if not events:
            return "Your schedule is clear for today! ✨"

        event_list = [
            f"- **{event['summary']}** at {dt.datetime.fromisoformat(event['start'].get('dateTime')).astimezone(user_tz).strftime('%I:%M %p')}"
            for event in events
        ]
        return "Here is your schedule for today:\n" + "\n".join(event_list)
    except Exception as e:
        return f"A system error occurred while fetching events: {e}"

def add_event(service, user_timezone_str, summary, start_time_str, end_time_str, description=None, location=None):
    """
    Takes timezone-naive time STRINGS from the AI and handles all timezone logic internally.
    """
    if not service: return "Error: Could not connect to Google Calendar."
    
    try:
        user_tz = pytz.timezone(user_timezone_str)

        start_dt_naive = dt.datetime.fromisoformat(start_time_str)
        end_dt_naive = dt.datetime.fromisoformat(end_time_str)

        start_dt_aware = user_tz.localize(start_dt_naive)
        end_dt_aware = user_tz.localize(end_dt_naive)
        
        conflict = _check_for_conflicts(service, start_dt_aware.isoformat(), end_dt_aware.isoformat(), user_tz_str)
        if conflict:
            return f"❌ Conflict detected. {conflict}."

        event_body = {
            'summary': summary,
            'location': location,
            'description': description or 'Scheduled by FocusFlow',
            'start': {'dateTime': start_dt_aware.isoformat()},
            'end': {'dateTime': end_dt_aware.isoformat()},
            'reminders': {'useDefault': True},
        }
        
        created_event = service.events().insert(calendarId='primary', body=event_body).execute()
        
        return (f"✅ Event '{summary}' was successfully added for "
                f"{start_dt_aware.strftime('%b %d at %I:%M %p')}.")

    except pytz.UnknownTimeZoneError:
        return f"❌ Error: The timezone '{user_timezone_str}' is invalid."
    except ValueError:
        return "❌ Failed to create event. The date/time format provided by the AI was incorrect."
    except HttpError as error:
        return f"❌ Failed to create event. Google Calendar API Error: {error}"
    except Exception as e:
        return f"❌ An unexpected error occurred: {e}"

def _check_for_conflicts(service, start_time_iso, end_time_iso, user_tz_str):
    """Internal helper function to check for conflicts."""
    if not service: return "Authentication service not available"
    try:
        events = service.events().list(
            calendarId='primary', 
            timeMin=start_time_iso, 
            timeMax=end_time_iso, 
            timeZone=user_tz_str, 
            singleEvents=True
        ).execute().get('items', [])
        return f"You already have '{events[0]['summary']}' scheduled" if events else None
    except Exception:
        return "Could not check for conflicts due to a system error."