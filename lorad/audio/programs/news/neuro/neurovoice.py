"""Compatibility imports for code using the old neurovoice module."""

from lorad.audio.programs.news.tts.service import (
    check_voiced,
    get_filelist,
    voice_news,
)

__all__ = ["check_voiced", "get_filelist", "voice_news"]
