# src/spotify_manager.py
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging
import os

logger = logging.getLogger(__name__)

class SpotifyManager:
    def __init__(self):
        # The scope defines the permissions we're asking for.
        # 'user-read-playback-state' is all we need for this feature.
        scope = "user-read-playback-state"
        
        # Spotipy will automatically read the client ID and secret from your .env file
        # because we named them SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET.
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                scope=scope,
                redirect_uri="http://localhost:8888/callback",
                open_browser=True # This will open a browser for the first-time login
            )
        )
        logger.info("SpotifyManager initialized.")

    def get_playback_state(self) -> dict | None:
        """
        Fetches the user's current playback state from Spotify.
        """
        try:
            logger.info("Fetching current Spotify playback state...")
            state = self.sp.current_playback()
            
            if state and state['is_playing'] and state['item']:
                track_info = {
                    "device_id": state['device']['id'],
                    "track_uri": state['item']['uri'],
                    "progress_ms": state['progress_ms'],
                    "is_playing": state['is_playing'],
                    "track_name": state['item']['name'],
                    "artist_name": state['item']['artists'][0]['name']
                }
                logger.info(f"Currently playing '{track_info['track_name']}' by {track_info['artist_name']}")
                return track_info
            else:
                logger.info("Spotify is not currently playing anything.")
                return None
        except Exception as e:
            # This will often be an authentication error on the first run.
            logger.error(f"Could not get Spotify playback state: {e}")
            logger.info("This might be the first time you're running this. A browser window should open for you to log in to Spotify.")
            return None