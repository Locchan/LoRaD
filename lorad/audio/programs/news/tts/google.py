from lorad.audio.programs.news.tts.base import (
    TTSConfigurationError,
    TTSProvider,
    TTSProviderError,
    TTSQuotaError,
)


class GoogleTTSProvider(TTSProvider):
    name = "google"

    def __init__(self, config: dict):
        credentials = config.get("GOOGLE_CLOUD_API_USERDATA")
        if not isinstance(credentials, dict) or not credentials:
            raise TTSConfigurationError("GOOGLE_CLOUD_API_USERDATA is required for Google TTS.")
        self.credentials = credentials
        self.language_code = config.get("GOOGLE_TTS_LANGUAGE", "ru-RU")
        self.voice_name = config.get("GOOGLE_TTS_VOICE", "ru-RU-Standard-B")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from google.cloud import texttospeech
        except ImportError as e:
            raise TTSConfigurationError(
                "google-cloud-texttospeech is required for Google TTS."
            ) from e
        self._client = texttospeech.TextToSpeechClient.from_service_account_info(
            self.credentials
        )
        return self._client

    def synthesize_mp3(self, text: str) -> bytes:
        try:
            from google.api_core.exceptions import ResourceExhausted
            from google.cloud import texttospeech
        except ImportError as e:
            raise TTSConfigurationError(
                "google-cloud-texttospeech is required for Google TTS."
            ) from e

        try:
            response = self._get_client().synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=texttospeech.VoiceSelectionParams(
                    language_code=self.language_code,
                    name=self.voice_name,
                    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                ),
            )
        except ResourceExhausted as e:
            raise TTSQuotaError("Google TTS quota is exhausted.") from e
        except TTSProviderError:
            raise
        except Exception as e:
            raise TTSProviderError("Google TTS request failed.") from e

        audio = response.audio_content
        if not audio:
            raise TTSProviderError("Google TTS returned empty audio.")
        return audio
