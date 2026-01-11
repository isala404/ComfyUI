"""Tests for MIME type utilities."""

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.mime import (
    guess_mime_type,
    get_extension_for_mime,
    get_output_type_from_mime,
    get_format_from_filename,
)


class TestGuessMimeType:
    """Tests for guess_mime_type function."""

    def test_image_types(self):
        """Test image MIME type detection."""
        assert guess_mime_type("image.png") == "image/png"
        assert guess_mime_type("image.jpg") == "image/jpeg"
        assert guess_mime_type("image.jpeg") == "image/jpeg"
        assert guess_mime_type("image.webp") == "image/webp"
        assert guess_mime_type("image.gif") == "image/gif"

    def test_audio_types(self):
        """Test audio MIME type detection."""
        assert guess_mime_type("audio.flac") == "audio/flac"
        assert guess_mime_type("audio.mp3") == "audio/mpeg"
        assert guess_mime_type("audio.wav") == "audio/wav"
        assert guess_mime_type("audio.ogg") == "audio/ogg"
        assert guess_mime_type("audio.opus") == "audio/opus"

    def test_video_types(self):
        """Test video MIME type detection."""
        assert guess_mime_type("video.mp4") == "video/mp4"
        assert guess_mime_type("video.webm") == "video/webm"
        assert guess_mime_type("video.mov") == "video/quicktime"

    def test_3d_types(self):
        """Test 3D model MIME type detection."""
        assert guess_mime_type("model.glb") == "model/gltf-binary"
        assert guess_mime_type("model.gltf") == "model/gltf+json"
        assert guess_mime_type("model.obj") == "text/plain"

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert guess_mime_type("IMAGE.PNG") == "image/png"
        assert guess_mime_type("Audio.FLAC") == "audio/flac"

    def test_unknown_extension(self):
        """Test unknown extension returns octet-stream."""
        assert guess_mime_type("file.xyz") == "application/octet-stream"

    def test_empty_filename(self):
        """Test empty filename."""
        assert guess_mime_type("") == "application/octet-stream"
        assert guess_mime_type(None) == "application/octet-stream"


class TestGetExtensionForMime:
    """Tests for get_extension_for_mime function."""

    def test_known_types(self):
        """Test known MIME type to extension mapping."""
        assert get_extension_for_mime("image/png") == ".png"
        assert get_extension_for_mime("image/jpeg") == ".jpg"
        assert get_extension_for_mime("audio/flac") == ".flac"
        assert get_extension_for_mime("video/mp4") == ".mp4"

    def test_unknown_type(self):
        """Test unknown MIME type returns None."""
        assert get_extension_for_mime("unknown/type") is None


class TestGetOutputTypeFromMime:
    """Tests for get_output_type_from_mime function."""

    def test_image_type(self):
        """Test image type detection."""
        assert get_output_type_from_mime("image/png") == "image"
        assert get_output_type_from_mime("image/jpeg") == "image"

    def test_audio_type(self):
        """Test audio type detection."""
        assert get_output_type_from_mime("audio/flac") == "audio"
        assert get_output_type_from_mime("audio/mpeg") == "audio"

    def test_video_type(self):
        """Test video type detection."""
        assert get_output_type_from_mime("video/mp4") == "video"
        assert get_output_type_from_mime("video/webm") == "video"

    def test_text_type(self):
        """Test text type detection."""
        assert get_output_type_from_mime("text/plain") == "text"
        assert get_output_type_from_mime("application/json") == "text"


class TestGetFormatFromFilename:
    """Tests for get_format_from_filename function."""

    def test_basic_formats(self):
        """Test basic format extraction."""
        assert get_format_from_filename("image.png") == "png"
        assert get_format_from_filename("audio.flac") == "flac"
        assert get_format_from_filename("video.mp4") == "mp4"

    def test_uppercase(self):
        """Test uppercase extensions."""
        assert get_format_from_filename("IMAGE.PNG") == "png"

    def test_no_extension(self):
        """Test filename without extension."""
        assert get_format_from_filename("filename") is None

    def test_empty(self):
        """Test empty filename."""
        assert get_format_from_filename("") is None
        assert get_format_from_filename(None) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
