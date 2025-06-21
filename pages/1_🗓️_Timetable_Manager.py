# pages/1_🗓️_Timetable_Manager.py
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta, time

# Import utilities from the main app directory
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import calendar_utils, timetable_parser

st.set_page_config(page_title="Timetable Manager", page_icon="🗓️")

st.title("🗓️ Timetable Manager")

# Check for authentication from the main app
if 'calendar_service' not in st.session_state or st.session_state.calendar_service is None:
    st.warning("Please connect to Google Calendar on the main 'FocusFlow - Chat' page first to use this feature.")
    st.link_button("Go to Login Page", "/")
    st.stop()
    
st.write("Upload an image of your class schedule, and I'll help you digitize it!")

# Initialize session state for the timetable DataFrame
if 'timetable_df' not in st.session_state:
    st.session_state.timetable_df = None

uploaded_file = st.file_uploader(
    "Choose a timetable image...", type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    image_bytes = uploaded_file.getvalue()
    st.image(image_bytes, caption="Your Uploaded Timetable", width=400)

    if st.button("Extract Schedule from Image", type="primary"):
        with st.spinner("Analyzing your timetable with AI... This might take a moment."):
            raw_response = timetable_parser.parse_timetable_image(image_bytes)
            if raw_response:
                try:
                    cleaned_response = raw_response.strip().replace("```json", "").replace("```", "")
                    data = json.loads(cleaned_response)
                    
                    if 'schedule' in data and data['schedule']:
                        df = pd.DataFrame(data['schedule'])
                        required_cols = ['day', 'subject', 'start_time', 'end_time']
                        if all(col in df.columns for col in required_cols):
                            st.session_state.timetable_df = df
                            st.success("Successfully extracted your schedule! You can now edit any details below before adding to your calendar.")
                        else:
                            st.error("The AI response was missing some required columns. Please try again.")
                            st.code(df.to_string())
                    else:
                        st.error("The AI could not find a valid schedule in the image.")
                        st.code(raw_response)
                except (json.JSONDecodeError, KeyError) as e:
                    st.error(f"Could not parse the AI's response: {e}")
                    st.code(raw_response)
            else:
                st.error("Failed to get a response from the AI.")

if st.session_state.timetable_df is not None:
    st.subheader("Extracted & Editable Schedule")
    
    edited_df = st.data_editor(
        st.session_state.timetable_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "day": st.column_config.SelectboxColumn("Day", options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], required=True),
            "subject": st.column_config.TextColumn("Subject", required=True),
            "start_time": st.column_config.TextColumn("Start Time (HH:MM)", required=True),
            "end_time": st.column_config.TextColumn("End Time (HH:MM)", required=True),
        }
    )
    
    st.session_state.timetable_df = edited_df

    if st.button("Add Edited Schedule to Google Calendar", type="primary"):
        df = st.session_state.timetable_df
        
        if df.empty or df.isnull().values.any():
            st.error("Your schedule is empty or has missing values. Please fill in all fields.")
            st.stop()
            
        total_events = len(df)
        progress_bar = st.progress(0, text="Starting to add events...")
        
        with st.spinner("Adding events to your calendar..."):
            day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
            today = datetime.now()
            
            service = st.session_state.calendar_service
            user_tz = st.session_state.user_profile['timezone']
            
            for index, row in df.iterrows():
                try:
                    day_name = str(row['day']).strip().capitalize()
                    days_ahead = day_map[day_name] - today.weekday()
                    if days_ahead < 0: days_ahead += 7
                    event_date = today + timedelta(days=days_ahead)
                    
                    # --- FIX: Robustly handle time data from st.data_editor ---
                    # It might be a string ("16:00") or a datetime.time object.
                    # We format it consistently to HH:MM.
                    start_time_obj = row['start_time']
                    end_time_obj = row['end_time']
                    
                    if isinstance(start_time_obj, time):
                        start_time_formatted = start_time_obj.strftime("%H:%M")
                    else:
                        start_time_formatted = str(start_time_obj)

                    if isinstance(end_time_obj, time):
                        end_time_formatted = end_time_obj.strftime("%H:%M")
                    else:
                        end_time_formatted = str(end_time_obj)

                    # Create the final naive timestamp strings
                    start_datetime_str = f"{event_date.strftime('%Y-%m-%d')}T{start_time_formatted}:00"
                    end_datetime_str = f"{event_date.strftime('%Y-%m-%d')}T{end_time_formatted}:00"

                    # --- FIX: Use the correct parameter names for the function call ---
                    result = calendar_utils.add_event(
                        service=service,
                        user_timezone_str=user_tz,
                        summary=str(row['subject']),
                        start_time_str=start_datetime_str,
                        end_time_str=end_datetime_str, # Corrected parameter name
                        description=f"Class from timetable - {day_name}"
                    )
                    
                    if result.startswith("✅"):
                        st.success(f"Added '{row['subject']}'")
                    else:
                        st.error(f"Failed to add '{row['subject']}': {result}")

                except Exception as e:
                    st.error(f"Failed to process row for '{row.get('subject', 'Unknown')}': {e}")
                
                progress_bar.progress((index + 1) / total_events)

        st.success("Timetable processing complete!")
        st.balloons()