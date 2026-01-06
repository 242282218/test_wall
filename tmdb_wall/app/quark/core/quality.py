import re
from typing import Optional

from app.quark.core.models import QualityInfo


class QualityEvaluator:
    """精简版画质评估"""

    def __init__(self):
        self.quality_patterns = {
            "UHD_4K": [r"4k", r"2160p", r"uhd", r"超高清"],
            "FHD_1080P": [r"1080p", r"fhd", r"全高清"],
            "HD_720P": [r"720p", r"hd", r"高清"],
            "SD_480P": [r"480p", r"sd", r"标清"],
            "LD_360P": [r"360p", r"流畅", r"低清"],
        }
        self.codec_patterns = {
            "HEVC": [r"hevc", r"h\.265", r"h265"],
            "H264": [r"h\.264", r"h264", r"avc"],
            "AV1": [r"av1"],
            "VP9": [r"vp9"],
        }
        self.hdr_patterns = [
            ("Dolby Vision", [r"dolby\s*vision", r"\bdovi\b", r"(?<![a-z0-9])dv(?![a-z0-9])"]),
            ("HDR10+", [r"hdr10\+", r"hdr10plus"]),
            ("HDR10", [r"\bhdr10\b"]),
            ("HDR", [r"\bhdr\b"]),
        ]
        self.sdr_patterns = [r"\bsdr\b", r"bt\.?709", r"rec\.?709"]
        self.dolby_audio_patterns = [r"\bdolby\b", r"\batmos\b", r"\btruehd\b", r"\bddp\b", r"\bdd\+\b"]

    def evaluate(self, name: str, size_raw: Optional[str] = None) -> QualityInfo:
        name_low = name.lower()
        level = self._detect_level(name_low)
        codec = self._detect_codec(name_low)
        hdr_format = self._detect_hdr_format(name_low)
        dolby_vision = hdr_format == "Dolby Vision"
        dolby_audio = self._detect_dolby_audio(name_low)
        dynamic_range = self._detect_dynamic_range(name_low, hdr_format, level)
        return QualityInfo(
            level=level,
            resolution=self._resolution(level),
            codec=codec,
            file_size=size_raw,
            total_size_gb=self._parse_size(size_raw) if size_raw else None,
            hdr_format=hdr_format,
            dynamic_range=dynamic_range,
            dolby_vision=dolby_vision,
            dolby_audio=dolby_audio,
        )

    def _detect_level(self, text: str) -> str:
        for level, patterns in self.quality_patterns.items():
            for p in patterns:
                if re.search(p, text, re.IGNORECASE):
                    return level
        return "UNKNOWN"

    def _detect_codec(self, text: str) -> Optional[str]:
        for codec, patterns in self.codec_patterns.items():
            for p in patterns:
                if re.search(p, text, re.IGNORECASE):
                    return codec
        return None

    def _resolution(self, level: str) -> str:
        mapping = {
            "UHD_4K": "4K",
            "FHD_1080P": "1080P",
            "HD_720P": "720P",
            "SD_480P": "480P",
            "LD_360P": "360P",
            "UNKNOWN": "Unknown",
        }
        return mapping.get(level, "Unknown")

    def _detect_hdr_format(self, text: str) -> Optional[str]:
        for name, patterns in self.hdr_patterns:
            for p in patterns:
                if re.search(p, text, re.IGNORECASE):
                    return name
        return None

    def _detect_dolby_audio(self, text: str) -> bool:
        for p in self.dolby_audio_patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    def _detect_dynamic_range(self, text: str, hdr_format: Optional[str], level: str) -> Optional[str]:
        if hdr_format:
            return "HDR"
        for p in self.sdr_patterns:
            if re.search(p, text, re.IGNORECASE):
                return "SDR"
        return "SDR" if level != "UNKNOWN" else None

    def _parse_size(self, size_raw: str) -> Optional[float]:
        """
        解析大小字符串为 GB（粗略）。
        例如 "10GB" / "1024MB".
        """
        try:
            m = re.match(r"([\d\.]+)\s*(gb|g|mb|m)", size_raw, re.IGNORECASE)
            if not m:
                return None
            val = float(m.group(1))
            unit = m.group(2).lower()
            if unit in ("gb", "g"):
                return val
            if unit in ("mb", "m"):
                return val / 1024.0
        except Exception:
            return None
        return None

