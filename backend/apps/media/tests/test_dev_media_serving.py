"""Tests for dev-only media serving with Content-Type sniffing.

Storage keys are extensionless (e.g. media/{uuid}/thumb), so Django's
default static view can't guess Content-Type.  ``sniff_image_content_type``
detects the format from magic bytes, and ``_serve_media`` wires it into
the dev serving path.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from django.test import RequestFactory

from apps.media.storage import sniff_image_content_type

# Minimal valid magic-byte sequences for each format.
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
WEBP_BYTES = b"RIFF" + struct.pack("<I", 20) + b"WEBP" + b"\x00" * 12
AVIF_BYTES = b"\x00\x00\x00\x1c" + b"ftypavif" + b"\x00" * 16


class TestSniffImageContentType:
    def test_jpeg(self):
        assert sniff_image_content_type(JPEG_BYTES) == "image/jpeg"

    def test_png(self):
        assert sniff_image_content_type(PNG_BYTES) == "image/png"

    def test_webp(self):
        assert sniff_image_content_type(WEBP_BYTES) == "image/webp"

    def test_avif(self):
        assert sniff_image_content_type(AVIF_BYTES) == "image/avif"

    def test_unknown_returns_none(self):
        assert sniff_image_content_type(b"\x00\x00\x00\x00" * 10) is None

    def test_empty_bytes_returns_none(self):
        assert sniff_image_content_type(b"") is None


def _write_file(root: Path, subpath: str, data: bytes) -> None:
    filepath = root / subpath
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(data)


@pytest.mark.django_db
class TestServeMediaView:
    """End-to-end tests for the _serve_media view function.

    Calls the actual view with a real file on disk and asserts
    Content-Type is correctly detected from magic bytes.
    """

    def _get_serve_media(self):
        from config.urls import _serve_media

        return _serve_media

    def _serve(self, tmp_path, subpath, data):
        _write_file(tmp_path, subpath, data)
        serve_media = self._get_serve_media()
        request = RequestFactory().get(f"/media/{subpath}")
        response = serve_media(request, path=subpath, document_root=str(tmp_path))
        # Close the underlying FileResponse to avoid ResourceWarning in tests.
        response.close()
        return response

    def test_jpeg_served_with_correct_content_type(self, tmp_path):
        resp = self._serve(tmp_path, "media/abc/original", JPEG_BYTES)
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/jpeg"

    def test_webp_served_with_correct_content_type(self, tmp_path):
        resp = self._serve(tmp_path, "media/abc/thumb", WEBP_BYTES)
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/webp"

    def test_avif_served_with_correct_content_type(self, tmp_path):
        resp = self._serve(tmp_path, "media/abc/original", AVIF_BYTES)
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/avif"

    def test_file_with_extension_not_sniffed(self, tmp_path):
        """Files that already have an extension get correct Content-Type
        from Django's default guessing — sniffing is skipped."""
        _write_file(tmp_path, "media/abc/photo.jpg", JPEG_BYTES)
        serve_media = self._get_serve_media()
        request = RequestFactory().get("/media/media/abc/photo.jpg")
        resp = serve_media(
            request, path="media/abc/photo.jpg", document_root=str(tmp_path)
        )
        resp.close()
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/jpeg"
