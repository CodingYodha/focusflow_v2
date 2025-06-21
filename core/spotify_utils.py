# core/spotify_utils.py
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth

@st.cache_resource
def get_spotify_client():
    """Authenticates with Spotify and returns a client object."""
    try:
        auth_manager = SpotifyOAuth(
            scope="user-read-private user-read-email",
            client_id=st.secrets["SPOTIPY_CLIENT_ID"],
            client_secret=st.secrets["SPOTIPY_CLIENT_SECRET"],
            redirect_uri=st.secrets["SPOTIPY_REDIRECT_URI"],
            cache_path=".spotify_cache" # Caches the token
        )
        spotify = spotipy.Spotify(auth_manager=auth_manager)
        return spotify
    except Exception as e:
        st.error(f"Could not connect to Spotify. Please check your credentials. Error: {e}")
        return None

def find_playlist(sp, mood_query, limit=1):
    """Finds a playlist on Spotify based on a mood query."""
    if not sp:
        return None, "Spotify connection not available."
    try:
        results = sp.search(q=mood_query, type='playlist', limit=limit)
        playlists = results['playlists']['items']
        if not playlists:
            return None, f"Could not find any playlists for '{mood_query}'."
        
        playlist = playlists[0]
        playlist_url = playlist['external_urls']['spotify']
        embed_url = playlist_url.replace("/playlist/", "/embed/playlist/")
        
        return embed_url, playlist['name']
    except Exception as e:
        return None, f"An error occurred while searching Spotify: {e}"