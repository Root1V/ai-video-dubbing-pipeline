"""Importa media desde una URL externa: descarga (para el pipeline), y
previsualizacion/busqueda (para el formulario de creacion de proyecto).

Usa yt-dlp para las 3 operaciones -- su extractor generico (`GenericIE`,
`_VALID_URL='.*'`) ya maneja tanto sitios soportados (YouTube, etc.) como
enlaces directos a archivos de video/audio con un unico code path, asi que no
hace falta una rama de descarga HTTP separada para "URL directa" vs "sitio".

No se modifica `application`/`domain`: este es un adaptador nuevo en `web/`,
igual que `storage.py` -- el use case de doblaje sigue asumiendo que el
archivo de entrada ya existe en disco al invocarse (`download_media` corre
ANTES, dentro de la tarea Celery, ver `tasks/run_project.py`).
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import yt_dlp
import yt_dlp.utils

from video_translator.web.config import WebSettings

_SEARCH_QUERY_MAX_LENGTH = 200
_SEARCH_LIMIT_MAX = 24
_LOOKUP_SOCKET_TIMEOUT = 15


class MediaImportError(Exception):
    """Fallo al previsualizar, buscar o descargar media desde una URL."""


class InvalidUrlError(MediaImportError):
    """La URL en si es invalida o esta bloqueada (esquema no http/https, o
    resuelve a una direccion no publica) -- distinto de un fallo de yt-dlp al
    intentar extraer/descargar una URL por lo demas valida, para que el
    router pueda devolver 422 vs 502 sin adivinar por el texto del mensaje."""


@dataclass
class MediaPreview:
    title: str
    thumbnail_url: str | None
    duration_seconds: float | None
    source_url: str
    is_youtube: bool
    youtube_video_id: str | None


def _validate_public_url(url: str) -> None:
    """Bloquea esquemas distintos a http/https y hosts que resuelven a una IP
    privada/loopback/link-local/reservada -- mitigacion de SSRF proporcional
    al contexto (proyecto interno, endpoints ya detras de autenticacion, no
    un SaaS multi-tenant publico).

    Limitacion consciente: esto solo valida el hostname en el momento de la
    llamada. yt-dlp hace sus propias peticiones de red con su propio stack, y
    puede seguir redirects o resolver DNS de nuevo despues de esta validacion
    (DNS rebinding / redirect a una IP interna). Cerrar eso del todo
    requeriria un Request Handler custom de yt-dlp -- fuera de alcance para
    este modelo de amenaza (el "atacante" es el propio dueno autenticado de
    su instancia, no un tercero anonimo).
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise InvalidUrlError("Solo se admiten URLs http:// o https://.")
    if not parts.hostname:
        raise InvalidUrlError("URL invalida.")

    try:
        addrinfo = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror as exc:
        raise InvalidUrlError(f"No se pudo resolver el host: {parts.hostname}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        ):
            raise InvalidUrlError("Esa URL apunta a una direccion no permitida.")


def _thumbnail_url(info: dict) -> str | None:
    # Con extract_flat=True (usado en search_youtube) yt-dlp no llena
    # "thumbnail" (queda None) -- solo la lista "thumbnails", ordenada de
    # menor a mayor resolucion. fetch_preview (extraccion completa, no flat)
    # si llena "thumbnail" directamente.
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbnails = info.get("thumbnails") or []
    return thumbnails[-1]["url"] if thumbnails else None


def _to_preview(info: dict) -> MediaPreview:
    # "extractor_key" se llena en extraccion completa (fetch_preview); en modo
    # flat (search_youtube, extract_flat=True) yt-dlp solo llena "ie_key" en
    # su lugar -- se chequean ambos para que la deteccion funcione en los dos
    # casos.
    is_youtube = info.get("extractor_key") == "Youtube" or info.get("ie_key") == "Youtube"
    return MediaPreview(
        title=info.get("title") or info.get("webpage_url") or "Sin titulo",
        thumbnail_url=_thumbnail_url(info),
        duration_seconds=info.get("duration"),
        source_url=info.get("webpage_url") or info.get("url") or "",
        is_youtube=is_youtube,
        youtube_video_id=info.get("id") if is_youtube else None,
    )


def fetch_preview(url: str) -> MediaPreview:
    """Extrae metadatos (titulo/miniatura/duracion) sin descargar nada."""
    _validate_public_url(url)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": _LOOKUP_SOCKET_TIMEOUT,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.YoutubeDLError as exc:
        raise MediaImportError(str(exc)) from exc
    if info is None:
        raise MediaImportError("No se pudo obtener informacion de esa URL.")
    return _to_preview(info)


def search_youtube(query: str, limit: int = 12) -> list[MediaPreview]:
    """Busca videos en YouTube por texto (sin API key de Google) usando el
    pseudo-URL `ytsearchN:` de yt-dlp."""
    query = query.strip()[:_SEARCH_QUERY_MAX_LENGTH]
    if not query:
        return []
    limit = max(1, min(limit, _SEARCH_LIMIT_MAX))

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "socket_timeout": _LOOKUP_SOCKET_TIMEOUT,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    except yt_dlp.utils.YoutubeDLError as exc:
        raise MediaImportError(str(exc)) from exc

    entries = (info or {}).get("entries") or []
    return [_to_preview(entry) for entry in entries if entry]


def download_media(url: str, project_id: UUID, settings: WebSettings) -> Path:
    """Descarga el media de `url` a `STORAGE_ROOT/uploads/{project_id}/` y
    devuelve la ruta final en disco."""
    _validate_public_url(url)

    upload_dir = Path(settings.storage_root) / "uploads" / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    def _abort_if_too_large(progress: dict) -> None:
        downloaded = progress.get("downloaded_bytes") or 0
        if downloaded > settings.download_max_bytes:
            raise yt_dlp.utils.DownloadCancelled(
                f"Excede el tamano maximo permitido ({settings.download_max_bytes} bytes)."
            )

    opts = {
        "outtmpl": str(upload_dir / "download.%(ext)s"),
        # Sitios como YouTube ya casi no exponen un unico stream progresivo
        # (video+audio muxeados) mas alla de resoluciones bajas -- forzar
        # solo "best[ext=mp4]/best" fallaba con "Requested format is not
        # available" en la mayoria de los videos actuales. bestvideo+bestaudio
        # cubre ese caso (yt-dlp mezcla los streams via ffmpeg, ya una
        # dependencia del proyecto), con "best" como ultimo fallback.
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "max_filesize": settings.download_max_bytes,
        "progress_hooks": [_abort_if_too_large],
        "socket_timeout": settings.download_timeout_seconds,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadCancelled as exc:
        for leftover in upload_dir.glob("download.*"):
            leftover.unlink(missing_ok=True)
        raise MediaImportError(str(exc)) from exc
    except yt_dlp.utils.YoutubeDLError as exc:
        raise MediaImportError(str(exc)) from exc

    if info is None:
        raise MediaImportError("No se pudo descargar esa URL.")

    requested = info.get("requested_downloads") or []
    filepath = (requested[-1].get("filepath") if requested else None) or info.get("filepath")
    if not filepath or not Path(filepath).exists():
        raise MediaImportError("La descarga no produjo un archivo valido.")

    return Path(filepath)
