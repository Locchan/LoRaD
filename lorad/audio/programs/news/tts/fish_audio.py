import requests

from lorad.audio.programs.news.tts.base import (
    TTSConfigurationError,
    TTSProvider,
    TTSProviderError,
    TTSQuotaError,
)

FISH_AUDIO_FREE_MODEL = "s2.1-pro-free"


class FishAudioTTSProvider(TTSProvider):
    name = "fish_audio"

    def __init__(self, config: dict):
        self.api_key = str(config.get("FISH_AUDIO_API_KEY", "")).strip()
        self.reference_id = str(config.get("FISH_AUDIO_REFERENCE_ID", "")).strip()
        self.base_url = str(
            config.get("FISH_AUDIO_BASE_URL", "https://api.fish.audio")
        ).rstrip("/")
        try:
            self.timeout_s = float(config.get("FISH_AUDIO_TIMEOUT_SECONDS", 120))
        except (TypeError, ValueError) as e:
            raise TTSConfigurationError(
                "FISH_AUDIO_TIMEOUT_SECONDS must be a number."
            ) from e

        if not self.api_key:
            raise TTSConfigurationError(
                "FISH_AUDIO_API_KEY is required for Fish Audio TTS."
            )
        if not self.reference_id:
            raise TTSConfigurationError(
                "FISH_AUDIO_REFERENCE_ID is required for Fish Audio TTS."
            )
        if not self.base_url.startswith(("https://", "http://")):
            raise TTSConfigurationError(
                "FISH_AUDIO_BASE_URL must be an HTTP or HTTPS URL."
            )
        if self.timeout_s <= 0:
            raise TTSConfigurationError(
                "FISH_AUDIO_TIMEOUT_SECONDS must be greater than zero."
            )

    def synthesize_mp3(self, text: str) -> bytes:
        if not text.strip():
            raise TTSProviderError("Fish Audio cannot synthesize empty text.")

        try:
            response = requests.post(
                f"{self.base_url}/v1/tts",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "model": FISH_AUDIO_FREE_MODEL,
                },
                json={
                    "text": text,
                    "reference_id": self.reference_id,
                    "format": "mp3",
                    "sample_rate": 44100,
                    "mp3_bitrate": 128,
                    "latency": "normal",
                    "normalize": True,
                },
                timeout=self.timeout_s,
            )
        except requests.Timeout as e:
            raise TTSProviderError("Fish Audio TTS request timed out.") from e
        except requests.RequestException as e:
            raise TTSProviderError("Fish Audio TTS request failed.") from e

        if response.status_code == 401:
            raise TTSConfigurationError("Fish Audio rejected the API key.")
        if response.status_code in (402, 429):
            raise TTSQuotaError("Fish Audio free-tier quota is unavailable.")
        if response.status_code == 503:
            raise TTSProviderError("Fish Audio is temporarily overloaded.")
        if not response.ok:
            raise TTSProviderError(
                f"Fish Audio TTS returned HTTP {response.status_code}."
            )
        if not response.content:
            raise TTSProviderError("Fish Audio returned empty audio.")
        return response.content
