# pages/1_🗓️_Timetable_Manager.py
import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta

# Import utilities from the main app directory
import sys
sys.path.append('..')
import timetable_parser
import calendar_utils

st.set_page_config(page_title="Timetable Manager", page_icon="🗓️")

# Initialize session state for timetable
if 'timetable_df' not in st.session_state:
    st.session_state.timetable_df = None

st.title("🗓️ Timetable Manager")
# Check for authentication from the main app
if 'calendar_service' not in st.session_state or st.session_state.calendar_service is None:
    st.warning("Please authenticate on the main 'FocusFlow - Chat' page first to use this feature.")
    st.stop()
    
st.write("Upload an image of your class schedule, and I'll help you digitize it!")


uploaded_file = st.file_uploader(
    "Choose a timetable image...", type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    image_bytes = uploaded_file.getvalue()
    st.image(image_bytes, caption="Your Uploaded Timetable", width=400)

    if st.button("Extract Schedule from Image", type="primary"):
        with st.spinner("Analyzing your timetable with AI... This might take a moment."):
            raw_response = timetable_parser.parse_timetable_image(image_bytes)
            try:
                # Clean the response to ensure it's valid JSON
                cleaned_response = raw_response.strip().replace("```json", "").replace("```", "")
                data = json.loads(cleaned_response)
                df = pd.DataFrame(data['schedule'])
                st.session_state.timetable_df = df
                st.success("Successfully extracted your schedule!")
            except (json.JSONDecodeError, KeyError) as e:
                st.error("The AI couldn't read the schedule properly. Please try a clearer image.")
                st.code(raw_response) # Show what the AI returned for debugging

if st.session_state.timetable_df is not None:
    st.subheader("Extracted Schedule")
    st.dataframe(st.session_state.timetable_df)

    if st.button("Add this schedule to my Google Calendar"):
        df = st.session_state.timetable_df
        total_events = len(df)
        progress_bar = st.progress(0, text="Starting to add events...")
        
        with st.spinner("Adding events to your calendar..."):
            day_map = {
                "Monday": 0, "Tuesday": 1, "Wednesday": 2, 
                "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6
            }
            today = datetime.now()
            
            for index, row in df.iterrows():
                try:
                    # Calculate the date of the next occurrence of this day
                    days_ahead = day_map[row['day']] - today.weekday()
                    if days_ahead < 0: days_ahead += 7
                    event_date = today + timedelta(days=days_ahead)
                    
                    start_datetime_str = f"{event_date.strftime('%Y-%m-%d')}T{row['start_time']}:00"
                    end_datetime_str = f"{event_date.strftime('%Y-%m-%d')}T{row['end_time']}:00"

                    # For simplicity, we are adding non-recurring events for the next upcoming day.
                    # A full implementation would add recurring events.
                    calendar_utils.add_event(
                        summary=row['subject'],
                        start_time=start_datetime_str,
                        end_time=end_datetime_str,
                        description="Recurring class from timetable."
                    )
                    progress_bar.progress((index + 1) / total_events, text=f"Added '{row['subject']}'")
                except Exception as e:
                    st.error(f"Failed to add '{row['subject']}': {e}")

        st.success("All classes have been added to your calendar for the upcoming week!")