from lorad.audio.programs.news.tts.base import TTSConfigurationError, TTSProvider
from lorad.common.utils.misc import read_config

_PROVIDER = None
_PROVIDER_NAME = None


def _provider_name(config: dict) -> str:
    name = str(config.get("NEWS_TTS_PROVIDER", "google")).strip().lower()
    aliases = {
        "fish": "fish_audio",
        "fishaudio": "fish_audio",
        "fish-audio": "fish_audio",
    }
    return aliases.get(name, name)


def create_tts_provider(config: dict) -> TTSProvider:
    name = _provider_name(config)
    if name == "google":
        from lorad.audio.programs.news.tts.google import GoogleTTSProvider

        return GoogleTTSProvider(config)
    if name == "fish_audio":
        from lorad.audio.programs.news.tts.fish_audio import FishAudioTTSProvider

        return FishAudioTTSProvider(config)
    raise TTSConfigurationError(
        f"Unknown NEWS_TTS_PROVIDER '{name}'. Expected 'google' or 'fish_audio'."
    )


def get_tts_provider(config=None) -> TTSProvider:
    global _PROVIDER, _PROVIDER_NAME
    config = config or read_config()
    name = _provider_name(config)
    if _PROVIDER is None or _PROVIDER_NAME != name:
        _PROVIDER = create_tts_provider(config)
        _PROVIDER_NAME = name
    return _PROVIDER


def reset_tts_provider():
    """Clear the cached provider after config reloads and in tests."""
    global _PROVIDER, _PROVIDER_NAME
    _PROVIDER = None
    _PROVIDER_NAME = None
