import os
import requests
import base64
import tempfile
from langdetect import detect
from app.config.logging import logger

SARVAM_API_KEY = os.getenv("SARVAM_AI_API_KEY")
SARVAM_API_BASE = 'https://api.sarvam.ai'

# Mapping from langdetect codes to Sarvam language codes
LANGUAGE_MAP = {
    'en': 'en-IN',
    'hi': 'hi-IN',
    'bn': 'bn-IN',
    'gu': 'gu-IN',
    'kn': 'kn-IN',
    'ml': 'ml-IN',
    'mr': 'mr-IN',
    'or': 'od-IN',  # Odia
    'pa': 'pa-IN',
    'ta': 'ta-IN',
    'te': 'te-IN',
}

def detect_language(text: str) -> str:
    """Detects the language of the text and returns the Sarvam code."""
    try:
        lang_code = detect(text)
        return LANGUAGE_MAP.get(lang_code, 'en-IN')  # Default to English
    except Exception as e:
        logger.error(f"Language detection failed: {e}")
        return 'en-IN'

def detect_language_sarvam(text: str) -> str:
    """Detects the language using Sarvam AI's detect-language API."""
    if not SARVAM_API_KEY:
        logger.error("SARVAM_AI_API_KEY not set. Using fallback language detection.")
        return detect_language(text)

    headers = {
        'Authorization': f'Bearer {SARVAM_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        "text": text
    }
    
    try:
        response = requests.post(f"{SARVAM_API_BASE}/detect-language", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        detected_lang = result.get('language_code', 'en-IN')
        logger.info(f"Detected language: {detected_lang}")
        return detected_lang
        
    except Exception as e:
        logger.error(f"Sarvam language detection failed: {e}")
        return detect_language(text)

def translate_text(text: str, target_language: str, source_language: str = None) -> str:
    """Translates text using Sarvam.ai API."""
    if not SARVAM_API_KEY:
        logger.error("SARVAM_AI_API_KEY not set. Translation unavailable.")
        return text

    # Auto-detect source language if not provided
    if source_language is None or source_language == 'auto':
        source_language = detect_language_sarvam(text)
    
    # If source and target languages are the same, return original text
    if source_language == target_language:
        return text

    headers = {
        'Authorization': f'Bearer {SARVAM_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "input": text,
        "source_language_code": source_language,
        "target_language_code": target_language,
        "speaker_gender": "Male",  # Optional: Male/Female
        "mode": "formal",  # Optional: formal/classic-colloquial/modern-colloquial
        "enable_preprocessing": True,  # Optional: better translations
        "output_script": None,  # Optional: null/roman/fully-native/spoken-form-in-native
        "numerals_format": "international"  # Optional: international/native
    }
    
    try:
        response = requests.post(f"{SARVAM_API_BASE}/translate", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        translated_text = result.get('translated_text', text)
        logger.info(f"Translation successful from {source_language} to {target_language}")
        return translated_text
        
    except Exception as e:
        logger.error(f"Sarvam translation failed: {e}")
        return text

def text_to_speech(text: str, language_code: str = 'en-IN', speaker: str = 'meera', model: str = 'bulbul:v1') -> str | None:
    """Converts text to speech using Sarvam.ai and returns the path to the audio file."""
    if not SARVAM_API_KEY:
        logger.error("SARVAM_AI_API_KEY not set. TTS unavailable.")
        return None

    headers = {
        'Authorization': f'Bearer {SARVAM_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Available speakers for bulbul:v1
    # Female: Diya, Maya, Meera, Pavithra, Maitreyi, Misha
    # Male: Amol, Arjun, Amartya, Arvind, Neel, Vian
    # For bulbul:v2
    # Female: Anushka, Manisha, Vidya, Arya  
    # Male: Abhilash, Karun, Hitesh
    
    payload = {
        "inputs": [text],  # Note: inputs is an array for multiple texts
        "target_language_code": language_code,
        "speaker": speaker,
        "pitch": 0.0,  # Range: -0.75 to 0.75
        "pace": 1.0,   # Range: 0.5 to 2.0
        "loudness": 1.0,  # Range: 0.3 to 3.0
        "speech_sample_rate": 22050,  # Options: 8000, 16000, 22050, 24000
        "enable_preprocessing": False,  # Better handling of mixed-language text
        "model": model  # Default: bulbul:v1
    }
    
    try:
        response = requests.post(f"{SARVAM_API_BASE}/text-to-speech", headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        audio_base64_list = result.get('audios', [])
        
        if not audio_base64_list:
            logger.error("TTS API did not return audio data.")
            return None

        # Get the first audio (since we sent one text)
        audio_base64 = audio_base64_list[0]
        audio_data = base64.b64decode(audio_base64)

        # Create temporary WAV file (Sarvam returns WAV format)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_data)
            logger.info(f"TTS audio saved to: {tmp_file.name}")
            return tmp_file.name

    except Exception as e:
        logger.error(f"Sarvam TTS failed: {e}")
        return None

def speech_to_text_translate(audio_file_path: str) -> str | None:
    """Transcribes speech to text and translates to English using Sarvam.ai API."""
    if not SARVAM_API_KEY:
        logger.error("SARVAM_AI_API_KEY not set. Speech-to-text translation unavailable.")
        return None

    headers = {
        'Authorization': f'Bearer {SARVAM_API_KEY}'
    }
    
    try:
        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'file': (audio_file_path, audio_file, 'audio/wav')
            }
            
            response = requests.post(
                f"{SARVAM_API_BASE}/speech-to-text-translate", 
                headers=headers, 
                files=files
            )
            response.raise_for_status()
            
            result = response.json()
            transcript = result.get('transcript', '')
            logger.info("Speech-to-text translation successful")
            return transcript
            
    except Exception as e:
        logger.error(f"Sarvam speech-to-text translation failed: {e}")
        return None

# Example usage functions
def example_usage():
    """Example usage of the Sarvam AI functions."""
    
    # Test text translation
    hindi_text = "नमस्ते, आप कैसे हैं?"
    english_translation = translate_text(hindi_text, target_language='en-IN', source_language='hi-IN')
    print(f"Hindi: {hindi_text}")
    print(f"English: {english_translation}")
    
    # Test TTS
    audio_file = text_to_speech("Hello, how are you today?", language_code='en-IN', speaker='meera')
    if audio_file:
        print(f"Audio file created: {audio_file}")
    
    # Test language detection
    detected_lang = detect_language_sarvam("Hello world")
    print(f"Detected language: {detected_lang}")

if __name__ == "__main__":
    example_usage()