"""Jerarquia de excepciones propias del dominio.

Aislar las excepciones de infraestructura (subprocess, httpx, etc.) detras de estas
clases permite que la capa de aplicacion y el CLI manejen errores de forma uniforme
sin acoplarse a detalles de implementacion.
"""


class VideoTranslatorError(Exception):
    """Excepcion base de la aplicacion."""


class InvalidVideoFileError(VideoTranslatorError):
    """El archivo de entrada no existe, no es legible o no es un formato soportado."""


class AudioExtractionError(VideoTranslatorError):
    """Fallo al extraer o preprocesar la pista de audio con ffmpeg."""


class TranscriptionError(VideoTranslatorError):
    """Fallo durante la transcripcion (Speech-to-Text)."""


class TranslationError(VideoTranslatorError):
    """Fallo durante la traduccion del texto (LLM)."""


class SynthesisError(VideoTranslatorError):
    """Fallo durante la sintesis de voz (Text-to-Speech) para doblaje."""


class DiarizationError(VideoTranslatorError):
    """Fallo durante la deteccion de hablantes (quien habla y cuando)."""


class MuxingError(VideoTranslatorError):
    """Fallo al combinar audio/subtitulos con el video final."""


class ConfigurationError(VideoTranslatorError):
    """Configuracion invalida o dependencia externa no disponible (ffmpeg, ollama, etc.)."""
