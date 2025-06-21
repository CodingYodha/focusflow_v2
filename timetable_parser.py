# core/timetable_parser.py
import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import json
import re

def parse_timetable_image(image_bytes):
    """Uses Gemini 1.5 Flash to parse a timetable image and return structured JSON."""
    try:
        # Configure the API key
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        img = Image.open(io.BytesIO(image_bytes))

        # Enhanced prompt with better instructions and validation
        prompt = """
        You are an expert timetable parser. Analyze the provided image of a class schedule/timetable.
        
        CRITICAL INSTRUCTIONS:
        1. Extract ALL visible classes/subjects from the timetable
        2. For each class, identify: day of week, subject name, start time, end time
        3. Times must be in 24-hour HH:MM format (e.g., "09:00", "14:30")
        4. Days must be full day names (e.g., "Monday", "Tuesday", not "Mon", "Tue")
        5. If you see abbreviations, expand them to full day names
        6. If times are in 12-hour format, convert to 24-hour format
        
        REQUIRED JSON STRUCTURE:
        {
          "schedule": [
            {
              "day": "Monday",
              "subject": "Physics",
              "start_time": "09:00",
              "end_time": "10:00"
            }
          ]
        }
        
        VALIDATION RULES:
        - day: Must be one of ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        - subject: The full subject/class name as it appears
        - start_time: 24-hour format HH:MM (00:00 to 23:59)
        - end_time: 24-hour format HH:MM (00:00 to 23:59)
        
        Return ONLY the JSON object. No explanations, no markdown formatting, no other text.
        """
        
        response = model.generate_content([prompt, img])
        raw_text = response.text.strip()
        
        # Clean up the response
        cleaned_response = clean_json_response(raw_text)
        
        # Validate the JSON structure
        try:
            data = json.loads(cleaned_response)
            validated_data = validate_schedule_data(data)
            return json.dumps(validated_data)
        except (json.JSONDecodeError, ValueError) as e:
            st.error(f"JSON parsing error: {e}")
            return raw_text  # Return raw text for debugging
            
    except Exception as e:
        st.error(f"An error occurred during image parsing: {e}")
        return None

def clean_json_response(raw_text):
    """Clean and extract JSON from the AI response."""
    # Remove markdown code blocks
    cleaned = re.sub(r'```json\s*', '', raw_text)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    
    # Remove any leading/trailing whitespace
    cleaned = cleaned.strip()
    
    # Try to find JSON object if there's extra text
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)
    
    return cleaned

def validate_schedule_data(data):
    """Validate and clean the schedule data."""
    if not isinstance(data, dict) or 'schedule' not in data:
        raise ValueError("Response must contain a 'schedule' key")
    
    schedule = data['schedule']
    if not isinstance(schedule, list):
        raise ValueError("Schedule must be a list")
    
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    validated_schedule = []
    
    for i, item in enumerate(schedule):
        if not isinstance(item, dict):
            continue
            
        # Check required fields
        required_fields = ['day', 'subject', 'start_time', 'end_time']
        if not all(field in item for field in required_fields):
            st.warning(f"Skipping item {i+1}: missing required fields")
            continue
        
        # Validate and clean day
        day = str(item['day']).strip().title()
        day_mapping = {
            'Mon': 'Monday', 'Tue': 'Tuesday', 'Wed': 'Wednesday',
            'Thu': 'Thursday', 'Fri': 'Friday', 'Sat': 'Saturday', 'Sun': 'Sunday',
            'Monday': 'Monday', 'Tuesday': 'Tuesday', 'Wednesday': 'Wednesday',
            'Thursday': 'Thursday', 'Friday': 'Friday', 'Saturday': 'Saturday', 'Sunday': 'Sunday'
        }
        
        if day in day_mapping:
            day = day_mapping[day]
        elif day not in valid_days:
            st.warning(f"Invalid day '{day}' in item {i+1}, skipping")
            continue
        
        # Validate and clean times
        start_time = validate_time_format(str(item['start_time']).strip())
        end_time = validate_time_format(str(item['end_time']).strip())
        
        if not start_time or not end_time:
            st.warning(f"Invalid time format in item {i+1}, skipping")
            continue
        
        # Clean subject name
        subject = str(item['subject']).strip()
        if not subject:
            st.warning(f"Empty subject in item {i+1}, skipping")
            continue
        
        validated_schedule.append({
            'day': day,
            'subject': subject,
            'start_time': start_time,
            'end_time': end_time
        })
    
    return {'schedule': validated_schedule}

def validate_time_format(time_str):
    """Validate and convert time to HH:MM format."""
    # Remove extra spaces and common suffixes
    time_str = re.sub(r'\s*(AM|PM|am|pm)\s*', '', time_str)
    
    # Try different time formats
    time_patterns = [
        r'^(\d{1,2}):(\d{2})$',  # HH:MM or H:MM
        r'^(\d{1,2})(\d{2})$',   # HHMM or HMM
        r'^(\d{1,2})\.(\d{2})$', # HH.MM or H.MM
    ]
    
    for pattern in time_patterns:
        match = re.match(pattern, time_str)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            
            # Validate ranges
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                return f"{hours:02d}:{minutes:02d}"
    
    # If no pattern matches, try to parse common formats
    try:
        from datetime import datetime
        # Try parsing with common formats
        for fmt in ['%H:%M', '%I:%M', '%H%M', '%I%M']:
            try:
                parsed_time = datetime.strptime(time_str, fmt)
                return parsed_time.strftime('%H:%M')
            except ValueError:
                continue
    except:
        pass
    
    return None