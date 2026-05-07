from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name, str(default)).lower()
    return value in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class ServerConfig:
    name: str = "127.0.0.1"
    port: int = 7860
    inbrowser: bool = True
    share: bool = False

@dataclass(frozen=True)
class TTSConfig:
    provider: str = "auto"
    edge_voice: str = ""
    edge_rate: str = ""


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "none"
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@dataclass(frozen=True)
class VisionConfig:
    provider: str = "none"
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@dataclass(frozen=True)
class MediaGenConfig:
    provider: str = "none"
    api_key: str = ""
    base_url: str = ""
    image_model: str = ""
    video_model: str = ""


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_env: str
    server: ServerConfig
    tts: TTSConfig
    llm: LLMConfig
    vision: VisionConfig
    media_gen: MediaGenConfig


def get_app_config() -> AppConfig:
    return AppConfig(
        app_name=_env("APP_NAME", "AI全自动剪辑工具"),
        app_env=_env("APP_ENV", "demo"),
        server=ServerConfig(
            name=_env("SERVER_NAME", "127.0.0.1"),
            port=_env_int("SERVER_PORT", 7860),
            inbrowser=_env_bool("INBROWSER", True),
            share=_env_bool("GRADIO_SHARE", False),
        ),
        tts=TTSConfig(
            provider=_env("TTS_PROVIDER", "auto").lower(),
            edge_voice=_env("TTS_EDGE_VOICE"),
            edge_rate=_env("TTS_EDGE_RATE"),
        ),
        llm=LLMConfig(
            provider=_env("LLM_PROVIDER", "none").lower(),
            api_key=_env("LLM_API_KEY"),
            base_url=_env("LLM_BASE_URL"),
            model=_env("LLM_MODEL"),
        ),
        vision=VisionConfig(
            provider=_env("VISION_PROVIDER", "none").lower(),
            api_key=_env("VISION_API_KEY"),
            base_url=_env("VISION_BASE_URL"),
            model=_env("VISION_MODEL"),
        ),
        media_gen=MediaGenConfig(
            provider=_env("MEDIA_GEN_PROVIDER", "none").lower(),
            api_key=_env("MEDIA_GEN_API_KEY"),
            base_url=_env("MEDIA_GEN_BASE_URL"),
            image_model=_env("MEDIA_GEN_IMAGE_MODEL"),
            video_model=_env("MEDIA_GEN_VIDEO_MODEL"),
        ),
    )
