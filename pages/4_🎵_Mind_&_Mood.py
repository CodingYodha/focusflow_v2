# pages/4_🎵_Mind_&_Mood.py
import streamlit as st
from datetime import datetime, timedelta
import random

# Import from core directory
from core import spotify_utils

st.set_page_config(page_title="Mind & Mood", page_icon="🎵")
st.title("🎵 Mind & Mood")
st.write("Check in with your feelings. A little music can make a big difference.")

# Initialize session state for this page
if 'mood_log' not in st.session_state:
    st.session_state.mood_log = []
if 'last_mood_suggestion' not in st.session_state:
    st.session_state.last_mood_suggestion = None

# Agentic Step: Check for persistent negative mood
negative_moods_in_last_3_days = 0
three_days_ago = datetime.now() - timedelta(days=3)
for log in st.session_state.mood_log:
    if log['timestamp'] > three_days_ago and log['mood'] in ["😔 Stressed", "😠 Frustrated"]:
        negative_moods_in_last_3_days += 1

if negative_moods_in_last_3_days >= 3:
    st.info("""
    **A note from your FocusFlow Coach...**
    
    "Hey, I've noticed things might have been a bit tough recently. Remember that it's completely okay to not be okay, and taking a moment to talk to someone can make a world of difference. Your well-being is the top priority."
    
    *Here are some resources if you ever feel like reaching out (these are examples):*
    - [BetterHelp Online Counseling](https://www.betterhelp.com/)
    - [7 Cups - Free Online Therapy & Chat](https://www.7cups.com/)
    """)

st.divider()

st.subheader("How are you feeling right now?")

mood_options = {
    "😄 Happy": {"query": ["happy", "upbeat", "good vibes"], "color": "#28a745"},
    "🙂 Focused": {"query": ["lofi", "deep focus", "instrumental study"], "color": "#007bff"},
    "😔 Stressed": {"query": ["calm", "ambient", "stress relief"], "color": "#ffc107"},
    "😠 Frustrated": {"query": ["soothing", "de-stress", "peaceful piano"], "color": "#dc3545"},
    "⚡ Energized": {"query": ["workout", "energy booster", "epic motivation"], "color": "#fd7e14"},
}

cols = st.columns(len(mood_options))
selected_mood = None

for i, (mood, props) in enumerate(mood_options.items()):
    if cols[i].button(mood, use_container_width=True):
        selected_mood = mood
        # Log the mood
        st.session_state.mood_log.append({"mood": mood, "timestamp": datetime.now()})
        st.toast(f"Mood logged as: {mood}", icon=mood.split(" ")[0])

if selected_mood:
    # Get a random query from the list to vary results
    query_term = random.choice(mood_options[selected_mood]['query'])
    
    with st.spinner(f"Finding the perfect '{query_term}' playlist for you..."):
        sp = spotify_utils.get_spotify_client()
        if sp:
            embed_url, playlist_name = spotify_utils.find_playlist(sp, query_term)
            st.session_state.last_mood_suggestion = (embed_url, playlist_name)
        else:
            st.error("Could not connect to Spotify to find music.")

if st.session_state.last_mood_suggestion:
    embed_url, playlist_name = st.session_state.last_mood_suggestion
    st.subheader(f"Here's a playlist for you: *{playlist_name}*")
    st.components.v1.iframe(embed_url, height=380)