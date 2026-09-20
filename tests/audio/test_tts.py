import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lorad.audio.programs.news.tts.base import (
    TTSConfigurationError,
    TTSProvider,
    TTSProviderError,
    TTSQuotaError,
)
from lorad.audio.programs.news.tts.factory import create_tts_provider
from lorad.audio.programs.news.tts.fish_audio import (
    FISH_AUDIO_FREE_MODEL,
    FishAudioTTSProvider,
)
from lorad.audio.programs.news.tts.google import GoogleTTSProvider
from lorad.audio.programs.news.tts import service


class FakeProvider(TTSProvider):
    name = "fake"

    def __init__(self, audio=b"mp3-audio"):
        self.audio = audio

    def synthesize_mp3(self, text: str) -> bytes:
        return self.audio


class FishAudioProviderTests(unittest.TestCase):
    def config(self):
        return {
            "FISH_AUDIO_API_KEY": "secret",
            "FISH_AUDIO_REFERENCE_ID": "voice-id",
            "FISH_AUDIO_BASE_URL": "https://fish.invalid/",
            "FISH_AUDIO_TIMEOUT_SECONDS": 12,
            "FISH_AUDIO_MODEL": "s2.1-pro",
        }

    @patch("lorad.audio.programs.news.tts.fish_audio.requests.post")
    def test_uses_free_model_and_mp3_payload(self, post):
        post.return_value = Mock(status_code=200, ok=True, content=b"audio")
        provider = FishAudioTTSProvider(self.config())

        self.assertEqual(provider.synthesize_mp3("Текст"), b"audio")

        _, kwargs = post.call_args
        self.assertEqual(post.call_args.args[0], "https://fish.invalid/v1/tts")
        self.assertEqual(kwargs["headers"]["model"], FISH_AUDIO_FREE_MODEL)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["json"]["reference_id"], "voice-id")
        self.assertEqual(kwargs["json"]["format"], "mp3")
        self.assertEqual(kwargs["json"]["sample_rate"], 44100)
        self.assertEqual(kwargs["timeout"], 12)

    def test_requires_key_and_reference_id(self):
        with self.assertRaises(TTSConfigurationError):
            FishAudioTTSProvider({"FISH_AUDIO_REFERENCE_ID": "voice"})
        with self.assertRaises(TTSConfigurationError):
            FishAudioTTSProvider({"FISH_AUDIO_API_KEY": "key"})

    @patch("lorad.audio.programs.news.tts.fish_audio.requests.post")
    def test_maps_http_failures(self, post):
        provider = FishAudioTTSProvider(self.config())
        for status, error_type in (
            (401, TTSConfigurationError),
            (402, TTSQuotaError),
            (429, TTSQuotaError),
            (503, TTSProviderError),
            (500, TTSProviderError),
        ):
            with self.subTest(status=status):
                post.return_value = Mock(status_code=status, ok=False, content=b"")
                with self.assertRaises(error_type):
                    provider.synthesize_mp3("text")


class FactoryTests(unittest.TestCase):
    def test_selects_supported_providers(self):
        google = create_tts_provider(
            {
                "NEWS_TTS_PROVIDER": "google",
                "GOOGLE_CLOUD_API_USERDATA": {"type": "service_account"},
            }
        )
        fish = create_tts_provider(
            {
                "NEWS_TTS_PROVIDER": "fish",
                "FISH_AUDIO_API_KEY": "key",
                "FISH_AUDIO_REFERENCE_ID": "voice",
            }
        )
        self.assertEqual(google.name, "google")
        self.assertEqual(fish.name, "fish_audio")

    def test_rejects_unknown_provider(self):
        with self.assertRaises(TTSConfigurationError):
            create_tts_provider({"NEWS_TTS_PROVIDER": "unknown"})


class GoogleProviderTests(unittest.TestCase):
    def test_synthesizes_through_google_provider_contract(self):
        provider = GoogleTTSProvider(
            {
                "GOOGLE_CLOUD_API_USERDATA": {"type": "service_account"},
                "GOOGLE_TTS_LANGUAGE": "ru-RU",
                "GOOGLE_TTS_VOICE": "ru-RU-Standard-B",
            }
        )
        provider._client = Mock()
        provider._client.synthesize_speech.return_value = SimpleNamespace(
            audio_content=b"google-mp3"
        )

        self.assertEqual(provider.synthesize_mp3("Текст"), b"google-mp3")
        provider._client.synthesize_speech.assert_called_once()


class TTSServiceTests(unittest.TestCase):
    @staticmethod
    def unlink(path):
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return False

    def test_writes_provider_audio_atomically(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"RUNTIME_MEDIA_DIR": tmpdir}
            with (
                patch.object(service, "read_config", return_value=config),
                patch.object(service, "is_shm_path", return_value=True),
                patch.object(service, "unlink_shm", side_effect=self.unlink),
                patch.object(
                    service.News,
                    "get_news_by_id",
                    return_value=SimpleNamespace(body_prepared="Prepared text"),
                ),
            ):
                self.assertTrue(service.voice_news(7, provider=FakeProvider()))
                output = os.path.join(tmpdir, "neurovoice", "7.mp3")
                with open(output, "rb") as audio_file:
                    self.assertEqual(audio_file.read(), b"mp3-audio")
                self.assertFalse(os.path.exists(output + ".part"))

    def test_removes_partial_file_if_atomic_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"RUNTIME_MEDIA_DIR": tmpdir}
            with (
                patch.object(service, "read_config", return_value=config),
                patch.object(service, "is_shm_path", return_value=True),
                patch.object(service, "unlink_shm", side_effect=self.unlink),
                patch.object(
                    service.News,
                    "get_news_by_id",
                    return_value=SimpleNamespace(body_prepared="Prepared text"),
                ),
                patch.object(service.os, "replace", side_effect=OSError("replace failed")),
            ):
                self.assertFalse(service.voice_news(8, provider=FakeProvider()))
                output = os.path.join(tmpdir, "neurovoice", "8.mp3")
                self.assertFalse(os.path.exists(output))
                self.assertFalse(os.path.exists(output + ".part"))


if __name__ == "__main__":
    unittest.main()
