# pages/4_🎵_Mind_&_Mood.py
import streamlit as st
from datetime import datetime, timedelta
import random

# Import from the core directory
from core import spotify_utils

st.set_page_config(page_title="Mind & Mood", page_icon="🎵", layout="wide")

st.title("🎵 Mind & Mood")
st.write("Check in with your feelings. A little music can make a big difference.")

# --- SIMPLIFIED AUTHENTICATION CHECK ---
# The main app.py now handles the login. This page just checks the result.
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
try:
    if 'mood_log' not in st.session_state: st.session_state.mood_log = []
    negative_mood_count = 0
    three_days_ago = datetime.now() - timedelta(days=3)
    for log in st.session_state.mood_log:
        if 'timestamp' in log and 'mood' in log:
            if log['timestamp'] > three_days_ago and log['mood'] in ["😔 Stressed", "😠 Frustrated"]:
                negative_mood_count += 1
    if negative_mood_count >= 3:
        st.info(
            """
            **A note from your FocusFlow Coach...**
            
            "Hey, I've noticed things might have been a bit tough recently. Remember that it's completely okay to not be okay, and talking to someone can make a world of difference. Your well-being is the top priority."
            
            *Here are some helpful resources (examples):*
            - [BetterHelp Online Counseling](https://www.betterhelp.com/)
            - [7 Cups - Free Online Therapy & Chat](https://www.7cups.com/)
            """
        )
        st.divider()
except Exception as e:
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
for i, (mood, props) in enumerate(mood_options.items()):
    if cols[i].button(mood, use_container_width=True):
        selected_mood = mood
        st.session_state.mood_log.append({"mood": mood, "timestamp": datetime.now()})
        st.toast(f"Mood logged: {mood.split(' ')[0]}", icon=mood.split(" ")[0])

# --- SPOTIFY PLAYLIST LOGIC ---
if selected_mood:
    query_term = random.choice(mood_options[selected_mood]['query'])
    with st.spinner(f"Finding the perfect '{query_term}' playlist for you..."):
        embed_url, playlist_name = spotify_utils.find_playlist(st.session_state.spotify_client, query_term)
        if 'last_mood_suggestion' not in st.session_state: st.session_state.last_mood_suggestion = None
        if embed_url: st.session_state.last_mood_suggestion = (embed_url, playlist_name)
        else: st.error(f"Could not find a playlist for '{query_term}'."); st.session_state.last_mood_suggestion = None
        st.rerun()

# Display the last found playlist
if 'last_mood_suggestion' in st.session_state and st.session_state.last_mood_suggestion:
    embed_url, playlist_name = st.session_state.last_mood_suggestion
    st.subheader(f"Here's a playlist for you: *{playlist_name}*")
    st.components.v1.iframe(embed_url, height=380, scrolling=True)
    
    # FIX: Manage user expectations about song previews
    st.caption("Note: Full tracks require a Spotify Premium account active in this browser. Free users may hear 30-second previews.")