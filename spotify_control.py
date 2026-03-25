import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants for Spotify Authentication
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "user-modify-playback-state user-read-playback-state user-read-currently-playing"

def get_spotify_client():
    """
    Initializes and returns a Spotify client using OAuth2.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not found in .env file.")
        return None
        
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=False # Set to False for non-interactive use (will print URL if needed)
    )
    return spotipy.Spotify(auth_manager=auth_manager)

def play(query=None):
    """Plays a track, album, or playlist based on a search query, or resumes playback."""
    sp = get_spotify_client()
    if not sp: return
    
    try:
        if query:
            results = sp.search(q=query, limit=1, type="track")
            if results["tracks"]["items"]:
                track_uri = results["tracks"]["items"][0]["uri"]
                sp.start_playback(uris=[track_uri])
                print(f"Playing: {results['tracks']['items'][0]['name']} by {results['tracks']['items'][0]['artists'][0]['name']}")
            else:
                print(f"No results found for '{query}'.")
        else:
            sp.start_playback()
            print("Resumed playback.")
    except Exception as e:
        print(f"Error during play: {e}")

def pause():
    """Pauses the current playback."""
    sp = get_spotify_client()
    if not sp: return
    try:
        sp.pause_playback()
        print("Playback paused.")
    except Exception as e:
        print(f"Error during pause: {e}")

def skip():
    """Skips to the next track."""
    sp = get_spotify_client()
    if not sp: return
    try:
        sp.next_track()
        print("Skipped to next track.")
    except Exception as e:
        print(f"Error during skip: {e}")

def previous():
    """Skips back to the previous track."""
    sp = get_spotify_client()
    if not sp: return
    try:
        sp.previous_track()
        print("Skipped back to previous track.")
    except Exception as e:
        print(f"Error during previous: {e}")

def status():
    """Returns the currently playing track info."""
    sp = get_spotify_client()
    if not sp: return
    try:
        current = sp.current_playback()
        if current and current["is_playing"]:
            track = current["item"]
            print(f"Currently Playing: {track['name']} by {track['artists'][0]['name']}")
        else:
            print("Nothing is currently playing.")
    except Exception as e:
        print(f"Error getting status: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python spotify_control.py <command> [query]")
        print("Commands: play, pause, skip, previous, status")
        sys.exit(1)
        
    command = sys.argv[1].lower()
    query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
    
    if command == "play":
        play(query)
    elif command == "pause":
        pause()
    elif command == "skip":
        skip()
    elif command == "previous":
        previous()
    elif command == "status":
        status()
    else:
        print(f"Unknown command: {command}")
