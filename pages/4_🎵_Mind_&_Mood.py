# pages/4_🎵_Mind_&_Mood.py
import streamlit as st
from datetime import datetime, timedelta
import random

from core import spotify_utils

st.set_page_config(page_title="Mind & Mood", page_icon="🎵")
st.title("🎵 Mind & Mood")
st.write("Check in with your feelings. A little music can make a big difference.")

# --- INITIALIZATION ---
# Initialize session state for this page
if 'mood_log' not in st.session_state:
    st.session_state.mood_log = []
if 'last_mood_suggestion' not in st.session_state:
    st.session_state.last_mood_suggestion = None
if 'spotify_client' not in st.session_state:
    st.session_state.spotify_client = None

# Get the auth manager. This is cached and only created once.
auth_manager = spotify_utils.get_spotify_auth_manager()

# --- AUTHENTICATION FLOW ---
# Check if we have an authenticated client in our session state
if st.session_state.spotify_client is None:
    # Get the URL parameters from the redirect
    query_params = st.query_params
    auth_code = query_params.get("code")

    # State 1: User needs to log in
    if not auth_code:
        auth_url = auth_manager.get_authorize_url()
        st.warning("To get music recommendations, you need to connect to Spotify.")
        # Use st.link_button for a clean, direct link
        st.link_button("Login to Spotify", auth_url, type="primary")
        st.stop() # Stop the script until the user logs in

    # State 2: User has logged in, and Spotify has redirected back with a code
    else:
        with st.spinner("Connecting to Spotify..."):
            try:
                # Exchange the code for an access token
                token_info = auth_manager.get_access_token(auth_code, as_dict=False)
                # Create the client and save it to the session state
                st.session_state.spotify_client = spotipy.Spotify(auth_manager=auth_manager)
                # Clear the query params from the URL for a clean look
                st.query_params.clear()
                st.rerun() # Rerun the script to show the main page
            except Exception as e:
                st.error("Authentication failed. Please try logging in again.")
                st.exception(e)
                st.stop()


# --- MAIN APP LOGIC (This only runs if authentication is successful) ---
st.success("Successfully connected to Spotify!")

# Agentic Step: Check for persistent negative mood
# ... (This logic is correct and does not need changes)
negative_moods_in_last_3_days = 0
three_days_ago = datetime.now() - timedelta(days=3)
for log in st.session_state.mood_log:
    if log['timestamp'] > three_days_ago and log['mood'] in ["😔 Stressed", "😠 Frustrated"]:
        negative_moods_in_last_3_days += 1
if negative_moods_in_last_3_days >= 3:
    st.info("A note from your FocusFlow Coach...") # Your message here

st.divider()

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
for i, (mood, props) in enumerate(mood_options.items()):
    if cols[i].button(mood, use_container_width=True):
        selected_mood = mood
        st.session_state.mood_log.append({"mood": mood, "timestamp": datetime.now()})
        st.toast(f"Mood logged as: {mood}", icon=mood.split(" ")[0])

if selected_mood:
    query_term = random.choice(mood_options[selected_mood]['query'])
    with st.spinner(f"Finding the perfect '{query_term}' playlist for you..."):
        # Use the client from the session state
        embed_url, playlist_name = spotify_utils.find_playlist(st.session_state.spotify_client, query_term)
        if embed_url:
            st.session_state.last_mood_suggestion = (embed_url, playlist_name)
        else:
            st.error(f"Could not find a playlist for '{query_term}'.")

if st.session_state.last_mood_suggestion:
    embed_url, playlist_name = st.session_state.last_mood_suggestion
    st.subheader(f"Here's a playlist for you: *{playlist_name}*")
    st.components.v1.iframe(embed_url, height=380)