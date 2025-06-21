# pages/4_🎵_Mind_&_Mood.py
import streamlit as st
from datetime import datetime, timedelta
import random

# Import from the core directory
from core import spotify_utils

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Mind & Mood", page_icon="🎵", layout="wide")

st.title("🎵 Mind & Mood")
st.write("Check in with your feelings. A little music can make a big difference.")

# --- INITIALIZATION ---
# Initialize session state variables specific to this page if they don't exist
if 'mood_log' not in st.session_state:
    st.session_state.mood_log = []
if 'last_mood_suggestion' not in st.session_state:
    st.session_state.last_mood_suggestion = None

# --- AUTHENTICATION CHECK ---
# The main app.py now handles the login. This page just checks for the result.
# If the spotify_client object doesn't exist in the session state, the user is not logged in.
if "spotify_client" not in st.session_state or st.session_state.spotify_client is None:
    st.warning("To get music recommendations, you need to connect your Spotify account.")
    st.info("Please go to the main 'FocusFlow - Chat' page to log in to Spotify.")
    # Provide a convenient button to navigate back to the main page
    st.link_button("Go to Login Page", "/", type="primary")
    st.stop() # Halt execution of this page until the user is logged in

# --- MAIN PAGE LOGIC (This only runs if authentication is successful) ---
st.success("✓ Connected to Spotify! Let's find some tunes.")
st.divider()

# --- AGENTIC STEP: Proactive Mental Health Check-in ---
# This feature demonstrates the agent's ability to notice patterns and offer help.
try:
    negative_mood_count = 0
    three_days_ago = datetime.now() - timedelta(days=3)
    
    # Iterate through the mood log to find recent negative moods
    for log in st.session_state.mood_log:
        # Ensure log entries have the expected keys
        if 'timestamp' in log and 'mood' in log:
            if log['timestamp'] > three_days_ago and log['mood'] in ["😔 Stressed", "😠 Frustrated"]:
                negative_mood_count += 1

    # If 3 or more negative moods are logged in the last 3 days, show a message
    if negative_mood_count >= 3:
        st.info(
            """
            **A note from your FocusFlow Coach...**
            
            "Hey, I've noticed things might have been a bit tough recently. Remember that it's completely okay to not be okay, and taking a moment to talk to someone can make a world of difference. Your well-being is the top priority."
            
            *Here are some helpful resources if you ever feel like reaching out (examples):*
            - [BetterHelp Online Counseling](https://www.betterhelp.com/)
            - [7 Cups - Free Online Therapy & Chat](https://www.7cups.com/)
            """
        )
        st.divider()
except Exception as e:
    # This prevents the app from crashing if the mood_log format is ever unexpected
    print(f"Error processing mood log for agentic check-in: {e}")


# --- MOOD SELECTION UI ---
st.subheader("How are you feeling right now?")
mood_options = {
    "😄 Happy": {"query": ["happy", "upbeat", "good vibes"]},
    "🙂 Focused": {"query": ["lofi", "deep focus", "instrumental study"]},
    "😔 Stressed": {"query": ["calm", "ambient", "stress relief"]},
    "😠 Frustrated": {"query": ["soothing", "de-stress", "peaceful piano"]},
    "⚡ Energized": {"query": ["workout", "energy booster", "epic motivation"]},
}

cols = st.columns(len(mood_options))
selected_mood = None

# Display mood buttons
for i, (mood, props) in enumerate(mood_options.items()):
    if cols[i].button(mood, use_container_width=True):
        selected_mood = mood
        # Log the mood with its timestamp
        st.session_state.mood_log.append({"mood": mood, "timestamp": datetime.now()})
        st.toast(f"Mood logged: {mood.split(' ')[0]}", icon=mood.split(" ")[0])

# --- SPOTIFY PLAYLIST LOGIC ---
# This block runs only when a mood button is clicked
if selected_mood:
    # Get a random search term from the list to vary the playlists
    query_term = random.choice(mood_options[selected_mood]['query'])
    
    with st.spinner(f"Finding the perfect '{query_term}' playlist for you..."):
        # Use the spotify_client object that was created on the main page
        embed_url, playlist_name = spotify_utils.find_playlist(st.session_state.spotify_client, query_term)
        
        if embed_url:
            st.session_state.last_mood_suggestion = (embed_url, playlist_name)
        else:
            st.error(f"Could not find a playlist for '{query_term}'. Please try another mood!")
            st.session_state.last_mood_suggestion = None
        
        # Rerun to immediately display the playlist or clear the old one
        st.rerun()

# Display the last found playlist
if st.session_state.last_mood_suggestion:
    embed_url, playlist_name = st.session_state.last_mood_suggestion
    st.subheader(f"Here's a playlist for you: *{playlist_name}*")
    st.components.v1.iframe(embed_url, height=380, scrolling=True)