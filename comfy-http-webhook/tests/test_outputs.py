"""Tests for output detection and processing."""

import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.outputs import detect_output_type
from core.types import OutputInfo


class TestDetectOutputType:
    """Tests for detect_output_type function."""

    def test_detect_images(self):
        """Test image output detection."""
        ui_output = {
            "images": [
                {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"},
                {"filename": "ComfyUI_00002_.png", "subfolder": "", "type": "output"},
            ]
        }
        outputs = detect_output_type(ui_output, node_id="5", node_type="SaveImage")

        assert len(outputs) == 2
        assert outputs[0].type == "image"
        assert outputs[0].filename == "ComfyUI_00001_.png"
        assert outputs[0].mime_type == "image/png"
        assert outputs[0].node_id == "5"
        assert outputs[0].node_type == "SaveImage"

    def test_detect_audio(self):
        """Test audio output detection."""
        ui_output = {
            "audio": [
                {"filename": "audio_00001_.flac", "subfolder": "audio", "type": "output"},
            ]
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 1
        assert outputs[0].type == "audio"
        assert outputs[0].filename == "audio_00001_.flac"
        assert outputs[0].mime_type == "audio/flac"

    def test_detect_video(self):
        """Test video output detection."""
        ui_output = {
            "video": [
                {"filename": "video_00001_.mp4", "subfolder": "", "type": "output"},
            ]
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 1
        assert outputs[0].type == "video"
        assert outputs[0].filename == "video_00001_.mp4"

    def test_detect_3d(self):
        """Test 3D mesh output detection."""
        ui_output = {
            "3d": [
                {"filename": "model_00001_.glb", "subfolder": "", "type": "output"},
            ]
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 1
        assert outputs[0].type == "mesh"
        assert outputs[0].filename == "model_00001_.glb"

    def test_detect_text_tuple(self):
        """Test text output detection (tuple format)."""
        ui_output = {
            "text": ("Hello world",)
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 1
        assert outputs[0].type == "text"
        assert outputs[0].inline_content == "Hello world"

    def test_detect_text_list(self):
        """Test text output detection (list format)."""
        ui_output = {
            "text": ["Generated caption"]
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 1
        assert outputs[0].type == "text"
        assert outputs[0].inline_content == "Generated caption"

    def test_detect_latents(self):
        """Test latent output detection."""
        ui_output = {
            "latents": [
                {"filename": "latent_00001_.latent", "subfolder": "", "type": "output"},
            ]
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 1
        assert outputs[0].type == "latent"

    def test_detect_result_3d_preview(self):
        """Test 3D preview (result) detection."""
        ui_output = {
            "result": ["model.glb", {"camera": "info"}, "bg.png"]
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 1
        assert outputs[0].type == "3d_preview"
        assert "model.glb" in outputs[0].inline_content

    def test_detect_mixed_outputs(self):
        """Test detecting multiple output types."""
        ui_output = {
            "images": [
                {"filename": "image.png", "subfolder": "", "type": "output"},
            ],
            "text": ("A caption",)
        }
        outputs = detect_output_type(ui_output)

        assert len(outputs) == 2
        types = [o.type for o in outputs]
        assert "image" in types
        assert "text" in types

    def test_detect_unknown_fallback(self):
        """Test fallback for unknown structures."""
        ui_output = {
            "custom_output": [
                {"filename": "custom.xyz", "subfolder": "", "type": "output"},
            ]
        }
        outputs = detect_output_type(ui_output)

        # Should extract unknown outputs
        assert len(outputs) >= 1

    def test_empty_output(self):
        """Test empty output handling."""
        outputs = detect_output_type({})
        assert len(outputs) == 0

        outputs = detect_output_type(None)
        assert len(outputs) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
