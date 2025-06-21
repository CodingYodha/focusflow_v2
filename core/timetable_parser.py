# core/timetable_parser.py
import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import json
import re

# This function should be in its own file: core/timetable_parser.py

def parse_timetable_image(image_bytes):
    """Uses Gemini 1.5 Flash to parse a timetable image and return structured JSON."""
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        img = Image.open(io.BytesIO(image_bytes))

        # Simplified prompt - let the validation code handle the rest
        prompt = """
        You are an expert timetable parser. Analyze the provided image of a class schedule.
        For each class, extract the day, subject, start time, and end time.
        Return the result ONLY as a valid JSON object with a single key "schedule" which is a list of objects.
        Each object must have the keys: "day", "subject", "start_time", "end_time".
        Times must be in 24-hour HH:MM format.
        
        Example:
        {
          "schedule": [
            { "day": "Monday", "subject": "Physics", "start_time": "09:00", "end_time": "10:00" }
          ]
        }
        """
        
        response = model.generate_content([prompt, img])
        return response.text
            
    except Exception as e:
        st.error(f"An error occurred during image parsing: {e}")
        return None