# core/spotify_utils.py
import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os

@st.cache_resource
def get_spotify_auth_manager():
    """
    Creates and returns the SpotifyOAuth manager object.
    This is cached so it's only created once per session.
    It reads credentials from Streamlit's secrets management.
    """
    # Define the cache path for the token
    # In Streamlit Cloud, this will be in a temporary directory.
    cache_path = ".spotify_cache"
    
    try:
        auth_manager = SpotifyOAuth(
            scope="user-read-private user-read-email", # Permissions we ask for
            client_id=st.secrets["SPOTIPY_CLIENT_ID"],
            client_secret=st.secrets["SPOTIPY_CLIENT_SECRET"],
            redirect_uri=st.secrets["SPOTIPY_REDIRECT_URI"],
            cache_path=cache_path,
            show_dialog=True # Ensures the user is always prompted for consent on first login
        )
        return auth_manager
    except Exception as e:
        st.error(f"Could not configure Spotify Authentication. Error: {e}")
        return None

def get_spotify_client(auth_manager):
    """
    Takes an auth_manager and tries to get a valid token and create a client.
    This is NOT cached, as its state depends on the OAuth flow.
    """
    if not auth_manager:
        return None
        
    try:
        # Check if a token is already cached
        token_info = auth_manager.get_cached_token()
        
        # If no token is found in the cache, the user needs to authenticate.
        # This function will return None, and the UI will show the login button.
        if not token_info:
            return None

        # If a token is found, create the client and return it.
        return spotipy.Spotify(auth_manager=auth_manager)
    
    except Exception as e:
        # This can happen if the cached token is invalid for some reason
        print(f"Error creating Spotify client from cached token: {e}")
        # To fix this, we can try to delete the corrupt cache file
        if os.path.exists(".spotify_cache"):
            os.remove(".spotify_cache")
        return None

def find_playlist(sp, mood_query, limit=1):
    """
    Finds a playlist on Spotify based on a mood query.
    """
    if not sp:
        return None, "Spotify connection not available."
    try:
        results = sp.search(q=mood_query, type='playlist', limit=limit)
        playlists = results['playlists']['items']
        if not playlists:
            return None, f"Could not find any playlists for '{mood_query}'."
        
        playlist = playlists[0]
        playlist_url = playlist['external_urls']['spotify']
        # Convert the standard URL to an embeddable one for Streamlit
        embed_url = playlist_url.replace("/playlist/", "/embed/playlist/")
        
        return embed_url, playlist['name']
    except Exception as e:
        return None, f"An error occurred while searching Spotify: {e}"