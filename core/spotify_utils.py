# core/spotify_utils.py
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# This function is now designed to be called once to set up the manager
@st.cache_resource
def get_spotify_auth_manager():
    """Creates and returns the SpotifyOAuth manager object."""
    try:
        auth_manager = SpotifyOAuth(
            scope="user-read-private user-read-email",
            client_id=st.secrets["SPOTIPY_CLIENT_ID"],
            client_secret=st.secrets["SPOTIPY_CLIENT_SECRET"],
            redirect_uri=st.secrets["SPOTIPY_REDIRECT_URI"],
            cache_path=".spotify_cache",
            show_dialog=True # Always show the consent dialog for clarity
        )
        return auth_manager
    except Exception as e:
        st.error(f"Could not configure Spotify. Error: {e}")
        return None

# We no longer cache the client, as its state depends on the auth flow
def get_spotify_client(auth_manager):
    """
    Takes an auth_manager and tries to get a valid token.
    If successful, returns a client object.
    """
    try:
        # Try to get a token from the cache
        token_info = auth_manager.get_cached_token()
        
        # If no token, or if it's expired, the user needs to authenticate.
        # This function will now simply return None, and the UI will handle it.
        if not token_info:
            return None

        return spotipy.Spotify(auth_manager=auth_manager)
    
    except Exception as e:
        print(f"Error creating Spotify client: {e}")
        return None

def find_playlist(sp, mood_query, limit=1):
    """Finds a playlist on Spotify based on a mood query."""
    # This function remains the same
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