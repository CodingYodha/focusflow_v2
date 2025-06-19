# audio_utils.py
import speech_recognition as sr
from gtts import gTTS
import io
import streamlit as st

def transcribe_audio_from_mic():
    """Captures audio from the microphone and transcribes it to text."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Speak now!")
        try:
            # Adjust for ambient noise once
            r.adjust_for_ambient_noise(source)
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            st.warning("Listening timed out. Please try again.")
            return ""

    try:
        st.info("Transcribing...")
        text = r.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        st.error("Sorry, I could not understand the audio.")
        return ""
    except sr.RequestError as e:
        st.error(f"Could not request results from Google Speech Recognition service; {e}")
        return ""

def text_to_speech_autoplay(text):
    """Converts text to speech and returns an audio element that autoplays."""
    try:
        tts = gTTS(text=text, lang='en')
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        
        # Use st.audio with autoplay=True
        return st.audio(audio_fp, format='audio/mp3', autoplay=True)
    except Exception as e:
        st.error(f"Failed to generate audio: {e}")
        return None