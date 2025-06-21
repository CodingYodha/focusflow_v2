# core/transcriber.py
import requests
from google.cloud import speech

def transcribe_telegram_voice_note(file_url):
    """Downloads a Telegram audio file and transcribes it using Google Cloud Speech-to-Text."""
    try:
        # Download the audio file from Telegram's temporary URL
        response = requests.get(file_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        audio_content = response.content

        # Initialize the Google Speech client
        client = speech.SpeechClient()

        audio = speech.RecognitionAudio(content=audio_content)
        # Telegram voice notes are encoded in OGG format with the Opus codec.
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=16000, # This is a standard for Telegram voice notes
            language_code="en-US",   # Or specify other languages if needed
        )

        # Performs speech recognition on the audio file
        response = client.recognize(config=config, audio=audio)

        if not response.results or not response.results[0].alternatives:
            return None # Return None if no transcription could be made

        # Return the most likely transcription
        return response.results[0].alternatives[0].transcript

    except Exception as e:
        print(f"Error during transcription: {e}")
        return None