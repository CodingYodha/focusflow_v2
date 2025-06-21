# timetable_parser.py
import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

def parse_timetable_image(image_bytes):
    """Uses Gemini 1.5 Flash to parse a timetable image and return structured JSON."""
    try:
        # It's good practice to re-configure the API key in each module that uses it.
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        img = Image.open(io.BytesIO(image_bytes))

        # --- FIX: Updated prompt to generate the correct column names ---
        prompt = """
        You are an expert timetable parser. Analyze the provided image of a class schedule.
        Extract the following information for each class or event:
        1.  `day`: The day of the week (e.g., "Monday", "Tuesday").
        2.  `subject`: The name of the subject or class.
        3.  `start_time`: The start time in 24-hour HH:MM format.
        4.  `end_time`: The end time in 24-hour HH:MM format.

        Return the result ONLY as a valid JSON object containing a list of these events.
        Do not include any other text, greetings, or markdown formatting.
        The JSON keys must be exactly `day`, `subject`, `start_time`, and `end_time`.
        
        Example output:
        {
          "schedule": [
            { "day": "Monday", "subject": "Physics", "start_time": "09:00", "end_time": "10:00" },
            { "day": "Monday", "subject": "Calculus", "start_time": "10:00", "end_time": "11:00" }
          ]
        }
        """
        
        response = model.generate_content([prompt, img])
        return response.text

    except Exception as e:
        st.error(f"An error occurred during image parsing: {e}")
        return None