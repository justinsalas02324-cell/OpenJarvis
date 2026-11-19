"""Fish Audio text-to-speech backend.

Uses the Fish Audio REST API (``POST /v1/tts``). Fish Audio supports cloned and
community voices, selected with a ``reference_id`` (the voice model ID shown in
the Fish Audio dashboard). Requires the ``FISH_AUDIO_API_KEY`` environment
variable or an ``api_key`` argument.
"""

from __future__ import annotations

import os
from typing import List

import httpx

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

_FISH_API_BASE = "https://api.fish.audio"

# ``model`` is sent as a request header. Leave it empty to let Fish Audio pick
# its current default; ``FISH_AUDIO_MODEL`` lets users pin one (for example
# ``s2.1-pro-free`` on the free developer tier) without a code change.
_SUPPORTED_FORMATS = {"mp3", "wav", "pcm", "opus"}
_MIN_SPEED = 0.5
_MAX_SPEED = 2.0


def _default_model() -> str:
    return os.environ.get("FISH_AUDIO_MODEL", "")


def _fish_synthesize(
    api_key: str,
    text: str,
    voice_id: str = "",
    model: str = "",
    output_format: str = "mp3",
    speed: float = 1.0,
) -> bytes:
    """Call the Fish Audio TTS API and return raw audio bytes."""
    fmt = output_format if output_format in _SUPPORTED_FORMATS else "mp3"
    headers = {"Authorization": f"Bearer {api_key}"}
    if model:
        headers["model"] = model

    body: dict = {"text": text, "format": fmt}
    if voice_id:
        body["reference_id"] = voice_id
    if speed != 1.0:
        body["prosody"] = {"speed": min(max(speed, _MIN_SPEED), _MAX_SPEED)}

    resp = httpx.post(
        f"{_FISH_API_BASE}/v1/tts",
        headers=headers,
        json=body,
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.content


@TTSRegistry.register("fish_audio")
class FishAudioTTSBackend(TTSBackend):
    """Fish Audio TTS backend — supports custom and cloned voices."""

    backend_id = "fish_audio"

    def __init__(self, *, api_key: str = "", model: str = "") -> None:
        self._api_key = api_key or os.environ.get("FISH_AUDIO_API_KEY", "")
        self._model = model or _default_model()

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
    ) -> TTSResult:
        if not self._api_key:
            raise RuntimeError("FISH_AUDIO_API_KEY not set")

        # No static default voice: without a ``reference_id`` Fish Audio uses
        # its own default voice. Set ``speech.voice_id`` to your voice model ID.
        audio = _fish_synthesize(
            self._api_key,
            text,
            voice_id=voice_id,
            model=self._model,
            output_format=output_format,
            speed=speed,
        )

        return TTSResult(
            audio=audio,
            format=output_format if output_format in _SUPPORTED_FORMATS else "mp3",
            voice_id=voice_id,
            sample_rate=44100,
            metadata={"backend": "fish_audio", "model": self._model},
        )

    def available_voices(self) -> List[str]:
        # Voices are user-specific model IDs from the Fish Audio dashboard,
        # so there is no fixed list to return.
        return []

    def health(self) -> bool:
        return bool(self._api_key)
