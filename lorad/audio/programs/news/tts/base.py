from abc import ABC, abstractmethod


class TTSProviderError(RuntimeError):
    """A provider failed to synthesize speech."""


class TTSConfigurationError(TTSProviderError):
    """A provider is unavailable because its configuration is invalid."""


class TTSQuotaError(TTSProviderError):
    """A provider rejected synthesis because its quota is exhausted."""


class TTSProvider(ABC):
    name = ""

    @abstractmethod
    def synthesize_mp3(self, text: str) -> bytes:
        """Return complete MP3 audio for text."""
