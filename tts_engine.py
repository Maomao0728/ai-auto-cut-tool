from __future__ import annotations

import asyncio
import platform
import re
import subprocess
import wave
from pathlib import Path

from typing import Any, cast

from api_config import get_app_config


def clean_tts_text(text: str) -> str:
    text = re.sub(r"\s+", "，", text.strip())
    text = text.replace("#", "")
    return text


def estimate_voice_duration(text: str, speed: int = 0) -> float:
    chars = len(re.sub(r"\s+", "", text))
    chars_per_second = 4.3 + speed * 0.25
    return max(chars / max(chars_per_second, 2.5), 3.0)


def _voice_keyword(voice_style: str) -> str:
    if "女" in voice_style or "温暖" in voice_style:
        return "Huihui"
    if "男" in voice_style or "沉稳" in voice_style:
        return "Kangkang"
    return "Huihui"


def _voice_rate(voice_style: str) -> int:
    if "年轻" in voice_style:
        return 1
    if "沉稳" in voice_style:
        return -1
    return 0


def _edge_voice(voice_style: str) -> str:
    configured = get_app_config().tts.edge_voice
    if configured:
        return configured
    if "男" in voice_style or "沉稳" in voice_style:
        return "zh-CN-YunxiNeural"
    if "年轻" in voice_style:
        return "zh-CN-XiaoyiNeural"
    return "zh-CN-XiaoxiaoNeural"


def _edge_rate(voice_style: str) -> str:
    configured = get_app_config().tts.edge_rate
    if configured:
        return configured
    if "年轻" in voice_style:
        return "+12%"
    if "沉稳" in voice_style:
        return "-8%"
    return "+0%"


def get_wav_duration(audio_path: Path) -> float:
    if not audio_path.exists():
        return 0.0
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate <= 0:
                return 0.0
            return frames / float(rate)
    except wave.Error:
        return 0.0


def get_audio_duration(audio_path: Path | None) -> float:
    if not audio_path or not audio_path.exists():
        return 0.0
    if audio_path.suffix.lower() == ".wav":
        return get_wav_duration(audio_path)
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    try:
        return float(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else 0.0
    except ValueError:
        return 0.0


def synthesize_windows_tts(text: str, output_wav: Path, voice_style: str) -> tuple[Path | None, str]:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    safe_text = clean_tts_text(text)
    if not safe_text:
        return None, "文案为空，无法生成配音。"

    voice_keyword = _voice_keyword(voice_style)
    rate = _voice_rate(voice_style)
    escaped_text = safe_text.replace("'", "''")
    escaped_path = str(output_wav).replace("'", "''")

    ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -like '*{voice_keyword}*' }} | Select-Object -First 1
if ($voice -ne $null) {{ $synth.SelectVoice($voice.VoiceInfo.Name) }}
$synth.Rate = {rate}
$synth.Volume = 100
$synth.SetOutputToWaveFile('{escaped_path}')
$synth.Speak('{escaped_text}')
$synth.Dispose()
"""
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0:
        return None, "Windows TTS 生成失败，可切换 edge-tts 或后续公司 TTS API。" + (result.stderr or result.stdout)
    if not output_wav.exists() or output_wav.stat().st_size == 0:
        return None, "Windows TTS 未生成有效音频，请检查系统语音组件。"
    return output_wav, "已使用 Windows 本地语音生成旁白。"


async def _run_edge_tts(text: str, output_mp3: Path, voice_style: str) -> None:
    edge_tts_module = cast(Any, __import__("edge_tts"))

    communicate = edge_tts_module.Communicate(clean_tts_text(text), voice=_edge_voice(voice_style), rate=_edge_rate(voice_style))
    await communicate.save(str(output_mp3))


def synthesize_edge_tts(text: str, output_mp3: Path, voice_style: str) -> tuple[Path | None, str]:
    output_mp3.parent.mkdir(parents=True, exist_ok=True)
    safe_text = clean_tts_text(text)
    if not safe_text:
        return None, "文案为空，无法生成配音。"
    try:
        asyncio.run(_run_edge_tts(safe_text, output_mp3, voice_style))
    except ImportError:
        return None, "edge-tts 未安装，请先安装 requirements.txt。"
    except Exception as exc:
        return None, f"edge-tts 生成失败：{exc}"
    if not output_mp3.exists() or output_mp3.stat().st_size == 0:
        return None, "edge-tts 未生成有效音频。"
    return output_mp3, f"已使用 edge-tts 在线语音生成旁白：{_edge_voice(voice_style)}。"


def synthesize_tts(text: str, output_dir: Path, voice_style: str) -> tuple[Path | None, str]:
    provider = get_app_config().tts.provider
    output_dir.mkdir(parents=True, exist_ok=True)

    if provider in {"none", "off", "disable", "disabled"}:
        return None, "已关闭 TTS，本次不生成旁白。"

    if provider == "edge":
        return synthesize_edge_tts(text, output_dir / "voiceover.mp3", voice_style)

    if provider == "windows":
        return synthesize_windows_tts(text, output_dir / "voiceover.wav", voice_style)

    if provider == "auto":
        if platform.system().lower() == "windows":
            voice_path, message = synthesize_windows_tts(text, output_dir / "voiceover.wav", voice_style)
            if voice_path:
                return voice_path, message
        edge_path, edge_message = synthesize_edge_tts(text, output_dir / "voiceover.mp3", voice_style)
        if edge_path:
            return edge_path, edge_message
        return None, edge_message

    return None, f"未知 TTS_PROVIDER：{provider}，请设置为 auto、windows、edge 或 none。"
