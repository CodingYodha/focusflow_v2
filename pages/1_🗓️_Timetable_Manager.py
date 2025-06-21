# pages/1_🗓️_Timetable_Manager.py
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta

# Import utilities from the main app directory
import sys
# This is a common pattern to ensure modules in the parent directory can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import calendar_utils
import timetable_parser

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
                    # Clean the response to ensure it's valid JSON
                    cleaned_response = raw_response.strip().replace("```json", "").replace("```", "")
                    data = json.loads(cleaned_response)
                    
                    # Validate that the expected structure exists
                    if 'schedule' not in data:
                        st.error("The AI response doesn't contain a 'schedule' field. Please try again.")
                        st.code(raw_response)
                    else:
                        df = pd.DataFrame(data['schedule'])
                        
                        # Validate required columns exist
                        required_columns = ['day', 'subject', 'start_time', 'end_time']
                        missing_columns = [col for col in required_columns if col not in df.columns]
                        
                        if missing_columns:
                            st.error(f"Missing required columns: {missing_columns}")
                            st.write("Available columns:", df.columns.tolist())
                            st.dataframe(df)
                        else:
                            st.session_state.timetable_df = df
                            st.success("Successfully extracted your schedule!")
                            
                except (json.JSONDecodeError, KeyError) as e:
                    st.error("The AI couldn't parse the schedule properly. Please try a clearer image or a different format.")
                    st.write("Error details:", str(e))
                    st.code(raw_response) # Show what the AI returned for debugging
            else:
                st.error("Failed to get a response from the AI. Please try again.")

if st.session_state.timetable_df is not None:
    st.subheader("Extracted Schedule")
    
    # Display the dataframe with editing capabilities
    edited_df = st.data_editor(
        st.session_state.timetable_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "day": st.column_config.SelectboxColumn(
                "Day",
                options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                required=True
            ),
            "subject": st.column_config.TextColumn("Subject", required=True),
            "start_time": st.column_config.TimeColumn("Start Time", format="HH:mm", required=True),
            "end_time": st.column_config.TimeColumn("End Time", format="HH:mm", required=True)
        }
    )
    
    # Update session state with edited data
    st.session_state.timetable_df = edited_df

    if st.button("Add this schedule to my Google Calendar", type="primary"):
        df = st.session_state.timetable_df
        
        # Validate data before processing
        if df.empty:
            st.error("No schedule data to add!")
            st.stop()
            
        # Check for missing values
        if df.isnull().any().any():
            st.error("Please fill in all empty fields before adding to calendar.")
            st.stop()
        
        total_events = len(df)
        progress_bar = st.progress(0, text="Starting to add events...")
        successful_additions = 0
        failed_additions = []
        
        with st.spinner("Adding events to your calendar..."):
            day_map = {
                "Monday": 0, "Tuesday": 1, "Wednesday": 2, 
                "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6
            }
            today = datetime.now()
            
            # Get the necessary context from the session state
            service = st.session_state.calendar_service
            user_tz = st.session_state.user_profile['timezone']

            for index, row in df.iterrows():
                try:
                    # Validate day value
                    day_name = str(row['day']).strip().capitalize()
                    if day_name not in day_map:
                        failed_additions.append(f"Row {index + 1}: Invalid day '{row['day']}'")
                        continue
                    
                    # Calculate the date of the next occurrence of this day
                    days_ahead = day_map[day_name] - today.weekday()
                    if days_ahead < 0: 
                        days_ahead += 7
                    event_date = today + timedelta(days=days_ahead)
                    
                    # Format times - handle both string and time objects
                    start_time = str(row['start_time'])
                    end_time = str(row['end_time'])
                    
                    # Ensure time format is correct (HH:MM)
                    if len(start_time) == 5 and ':' in start_time:
                        start_time_formatted = start_time
                    else:
                        # Try to parse and reformat if needed
                        try:
                            from datetime import datetime
                            parsed_time = datetime.strptime(start_time, "%H:%M:%S")
                            start_time_formatted = parsed_time.strftime("%H:%M")
                        except:
                            start_time_formatted = start_time
                    
                    if len(end_time) == 5 and ':' in end_time:
                        end_time_formatted = end_time
                    else:
                        try:
                            from datetime import datetime
                            parsed_time = datetime.strptime(end_time, "%H:%M:%S")
                            end_time_formatted = parsed_time.strftime("%H:%M")
                        except:
                            end_time_formatted = end_time
                    
                    # Create datetime strings in the format expected by calendar_utils
                    start_datetime_str = f"{event_date.strftime('%Y-%m-%d')}T{start_time_formatted}:00"
                    end_datetime_str = f"{event_date.strftime('%Y-%m-%d')}T{end_time_formatted}:00"

                    # Call add_event with the correct parameter names
                    result = calendar_utils.add_event(
                        service=service,
                        user_timezone_str=user_tz,
                        summary=str(row['subject']),
                        start_time_str=start_datetime_str,
                        end_time_str=end_datetime_str,
                        description=f"Class from timetable - {day_name}"
                    )
                    
                    # Update progress bar
                    progress_bar.progress((index + 1) / total_events, text=f"Processing '{row['subject']}'...")
                    
                    # Check if the result indicates success
                    if result.startswith("✅"):
                        successful_additions += 1
                        st.success(f"✅ Added '{row['subject']}' for {day_name}")
                    else:
                        failed_additions.append(f"'{row['subject']}': {result}")
                        st.error(f"❌ Failed to add '{row['subject']}': {result}")

                except Exception as e:
                    error_msg = f"'{row.get('subject', 'Unknown Event')}': {str(e)}"
                    failed_additions.append(error_msg)
                    st.error(f"❌ Failed to process '{row.get('subject', 'Unknown Event')}': {e}")

        # Final summary
        st.divider()
        if successful_additions > 0:
            st.success(f"🎉 Successfully added {successful_additions} out of {total_events} events to your calendar!")
        
        if failed_additions:
            st.error(f"❌ {len(failed_additions)} events failed to add:")
            for failure in failed_additions:
                st.write(f"• {failure}")
        
        if successful_additions == total_events:
            st.balloons()
            st.success("All events added successfully! 🎉")