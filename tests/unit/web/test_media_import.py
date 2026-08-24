"""Tests de web/services/media_import.py: validacion de SSRF, previsualizacion,
busqueda y descarga -- todos mockeando yt_dlp.YoutubeDL (no se hacen llamadas
de red reales)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import yt_dlp.utils

from video_translator.web.config import WebSettings
from video_translator.web.services.media_import import (
    InvalidUrlError,
    MediaImportError,
    download_media,
    fetch_preview,
    search_youtube,
)


class _FakeYoutubeDL:
    """Doble de `yt_dlp.YoutubeDL` que soporta el uso como context manager y
    devuelve `extract_info_result` (o lanza `extract_info_error`) tal como lo
    configure cada test."""

    def __init__(self, opts: dict) -> None:
        self.opts = opts

    def __enter__(self) -> _FakeYoutubeDL:  # noqa: PYI034 (typing.Self needs py311+)
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def extract_info(self, url: str, download: bool) -> dict | None:
        raise NotImplementedError


def _fake_ydl_returning(result: dict | None) -> type[_FakeYoutubeDL]:
    class _Fake(_FakeYoutubeDL):
        def extract_info(self, url: str, download: bool) -> dict | None:
            return result

    return _Fake


def _fake_ydl_raising(exc: Exception) -> type[_FakeYoutubeDL]:
    class _Fake(_FakeYoutubeDL):
        def extract_info(self, url: str, download: bool) -> dict | None:
            raise exc

    return _Fake


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:6379",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.com/video.mp4",
        "not-a-url",
    ],
)
def test_fetch_preview_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        fetch_preview(url)


def test_fetch_preview_youtube_maps_video_id() -> None:
    fake_info = {
        "title": "Un video",
        "thumbnail": "https://img.example/thumb.jpg",
        "duration": 125.0,
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
        "extractor_key": "Youtube",
        "id": "abc123",
    }
    with patch("yt_dlp.YoutubeDL", _fake_ydl_returning(fake_info)):
        preview = fetch_preview("https://www.youtube.com/watch?v=abc123")

    assert preview.title == "Un video"
    assert preview.is_youtube is True
    assert preview.youtube_video_id == "abc123"
    assert preview.duration_seconds == 125.0


def test_fetch_preview_non_youtube_has_no_video_id() -> None:
    fake_info = {
        "title": "archivo.mp4",
        "thumbnail": None,
        "duration": None,
        "webpage_url": "https://example.com/archivo.mp4",
        "extractor_key": "Generic",
        "id": "archivo",
    }
    with patch("yt_dlp.YoutubeDL", _fake_ydl_returning(fake_info)):
        preview = fetch_preview("https://example.com/archivo.mp4")

    assert preview.is_youtube is False
    assert preview.youtube_video_id is None


def test_fetch_preview_wraps_youtube_dl_errors() -> None:
    with patch(
        "yt_dlp.YoutubeDL",
        _fake_ydl_raising(yt_dlp.utils.DownloadError("Video no disponible")),
    ), pytest.raises(MediaImportError):
        fetch_preview("https://example.com/video.mp4")


def test_search_youtube_maps_entries_to_previews() -> None:
    # extract_flat=True (usado por search_youtube) llena "ie_key" (no
    # "extractor_key") y "thumbnails" -- una lista ordenada por resolucion
    # (no "thumbnail", que queda None) -- ver el fixture real capturado con
    # yt-dlp directamente. Un fixture con los nombres de campo "obvios" no
    # habria detectado el bug real (title/duracion se mostraban bien, pero
    # is_youtube/youtube_video_id/thumbnail_url quedaban vacios).
    fake_info = {
        "entries": [
            {
                "title": "Resultado 1",
                "thumbnail": None,
                "thumbnails": [{"url": "https://img.example/1-small.jpg"}, {"url": "https://img.example/1.jpg"}],
                "duration": 60.0,
                "webpage_url": "https://www.youtube.com/watch?v=r1",
                "ie_key": "Youtube",
                "id": "r1",
            },
            {
                "title": "Resultado 2",
                "thumbnail": None,
                "thumbnails": [{"url": "https://img.example/2.jpg"}],
                "duration": 90.0,
                "webpage_url": "https://www.youtube.com/watch?v=r2",
                "ie_key": "Youtube",
                "id": "r2",
            },
        ]
    }
    with patch("yt_dlp.YoutubeDL", _fake_ydl_returning(fake_info)):
        results = search_youtube("mi busqueda", limit=2)

    assert len(results) == 2
    assert results[0].title == "Resultado 1"
    assert results[0].thumbnail_url == "https://img.example/1.jpg"
    assert results[0].is_youtube is True
    assert results[1].youtube_video_id == "r2"


def test_search_youtube_empty_query_returns_empty_list() -> None:
    assert search_youtube("   ") == []


def test_download_media_success_via_requested_downloads(tmp_path: Path) -> None:
    settings = WebSettings(storage_root=str(tmp_path))
    project_id = uuid.uuid4()
    upload_dir = tmp_path / "uploads" / str(project_id)
    upload_dir.mkdir(parents=True)
    final_file = upload_dir / "download.mp4"
    final_file.write_bytes(b"fake-bytes")

    fake_info = {"requested_downloads": [{"filepath": str(final_file)}]}
    with patch("yt_dlp.YoutubeDL", _fake_ydl_returning(fake_info)):
        result = download_media("https://example.com/video.mp4", project_id, settings)

    assert result == final_file


def test_download_media_success_via_top_level_filepath(tmp_path: Path) -> None:
    settings = WebSettings(storage_root=str(tmp_path))
    project_id = uuid.uuid4()
    upload_dir = tmp_path / "uploads" / str(project_id)
    upload_dir.mkdir(parents=True)
    final_file = upload_dir / "download.mp4"
    final_file.write_bytes(b"fake-bytes")

    fake_info = {"filepath": str(final_file)}
    with patch("yt_dlp.YoutubeDL", _fake_ydl_returning(fake_info)):
        result = download_media("https://example.com/video.mp4", project_id, settings)

    assert result == final_file


def test_download_media_rejects_unsafe_url(tmp_path: Path) -> None:
    settings = WebSettings(storage_root=str(tmp_path))
    with pytest.raises(InvalidUrlError):
        download_media("http://127.0.0.1/video.mp4", uuid.uuid4(), settings)


def test_download_media_size_exceeded_raises_and_cleans_up(tmp_path: Path) -> None:
    settings = WebSettings(storage_root=str(tmp_path), download_max_bytes=10)
    project_id = uuid.uuid4()
    upload_dir = tmp_path / "uploads" / str(project_id)
    upload_dir.mkdir(parents=True)
    partial_file = upload_dir / "download.part"
    partial_file.write_bytes(b"partial")

    with patch(
        "yt_dlp.YoutubeDL",
        _fake_ydl_raising(yt_dlp.utils.DownloadCancelled("excede el tamano maximo")),
    ), pytest.raises(MediaImportError):
        download_media("https://example.com/big-video.mp4", project_id, settings)

    assert not partial_file.exists()


def test_download_media_generic_error_raises(tmp_path: Path) -> None:
    settings = WebSettings(storage_root=str(tmp_path))
    with patch(
        "yt_dlp.YoutubeDL",
        _fake_ydl_raising(yt_dlp.utils.DownloadError("no se pudo extraer")),
    ), pytest.raises(MediaImportError):
        download_media("https://example.com/video.mp4", uuid.uuid4(), settings)


def test_download_media_missing_filepath_raises(tmp_path: Path) -> None:
    settings = WebSettings(storage_root=str(tmp_path))
    with patch("yt_dlp.YoutubeDL", _fake_ydl_returning({})), pytest.raises(MediaImportError):
        download_media("https://example.com/video.mp4", uuid.uuid4(), settings)
