# Roadmap — detalle

Índice en [roadmap.md](../roadmap.md). Cada sección: **Why** (por qué existe) y **Scope** (qué incluye / qué queda fuera a propósito). No es una bitácora de cambios — eso vive en los commits.

## RM-01 — Transcripción standalone
**Why:** doblar/traducir es demasiado para alguien que solo quiere la transcripción del audio original.
**Scope:** audio o video de entrada; salida SRT + texto plano; sin traducción ni TTS.
Commit: `7064d5a`

## RM-02 — TTS standalone
**Why:** sintetizar voz a partir de texto es un caso de uso propio, no solo un paso interno del doblaje.
**Scope:** texto → audio; voz pública (masculina/femenina) o WAV propio; sin traducción.
Commits: `d047334`, `09a924d`

## RM-03 — Analítica de negocio
**Why:** el dashboard mostraba stats fijos en "—"; sin datos reales no sirve para decisiones de negocio.
**Scope:** `ProjectMetrics` persiste al borrar el proyecto; agregados (proyectos, minutos, idiomas) en `GET /dashboard/stats`.
Commit: `c13d6ea`

## RM-04 — Página de subtítulos
**Why:** `/subtitles/new` era un placeholder; el servicio ya existía en el backend.
**Scope:** formulario real con selector de modo de salida (solo SRT / incrustados / seleccionables).
Commit: `b5d4a87`

## RM-05 — Previsualización de media
**Why:** descargar un artefacto a ciegas para saber si el resultado es el esperado es mala UX.
**Scope:** reproductor de video/audio inline en cualquier vista con un artefacto descargable.
Commit: `63787a5`

## RM-06 — Waveform reactivo en vivo
**Why:** animación que reacciona al audio real durante la reproducción, no un spinner genérico.
**Scope:** barras que revelan la forma real de onda según avanza la reproducción, mezcladas con RMS en vivo cerca del cabezal.
Commits: `205cab7`, `c34df3b`, `73575e9`, `d18ec9c`

## RM-07 — Importar proyecto desde URL
**Why:** el cliente suele compartir un link (directo o de YouTube), no siempre un archivo local.
**Scope:** subir archivo / pegar URL / buscar en YouTube conviven en el mismo formulario (no se reemplazan); descarga vía yt-dlp con validación SSRF; previsualización antes de confirmar.
Commits: `f88d8ea`, `33f07ab`, `115adfc`, `396ba5e`

## RM-08 — Atribución correcta de fallos de etapa
**Why:** una etapa que crasheaba se registraba igual como "completada", así que la UI culpaba a la siguiente etapa del fallo real.
**Scope:** `PipelineTimings.stage()` ya no marca una etapa como completada si el bloque lanza una excepción; el frontend prioriza el paso "activo" sobre el primer "pendiente" al decidir cuál marcar como fallido.
Commit: `5d02d64`

## RM-09 — Librería de voces persistente
**Why:** hoy cada proyecto de doblaje/TTS sube su propia referencia de voz; no hay forma de guardar y reusar una.
**Scope:** tabla `Voice(user_id, name, wav_path, gender, language)` + selector reutilizable en doblaje/TTS. Las voces públicas actuales pueden vivir ahí como filas "del sistema".

## RM-10 — Plantillas reutilizables
**Why:** reconfigurar glosario/tono/contexto/idiomas en cada proyecto nuevo es repetitivo para un mismo tipo de contenido.
**Scope:** guardar el `config` de un proyecto como plantilla nombrada; aplicarla al crear uno nuevo.

## RM-11 — Documento → audio narrado
**Why:** nicho B2C (estudiantes/investigadores) que quiere un resumen narrado de un documento, no doblaje de video.
**Scope:** sin diseñar todavía — requiere un paso de resumen (LLM) que hoy no existe en ningún puerto; necesita su propia sesión de diseño antes de construirse.

## RM-12 — API para desarrolladores
**Why:** se retoma si el negocio gana tracción y aparecen integradores que la pidan explícitamente.
**Scope:** auth por API key + rate limiting; canal medido por uso, separado del dashboard.

## RM-13 — Workspace multi-usuario + facturación
**Why:** hoy es single-owner con roles admin/member, sin pagos; una empresa con varios usuarios necesitaría esto.
**Scope:** se revisa solo si hay tracción real con un primer cliente B2B — contradice la restricción vigente de "sin facturación".

## RM-14 — Imagen+texto → micro-video social
**Why:** idea de negocio B2C (shorts/reels desde imágenes + texto de venta) fuera de la arquitectura actual.
**Scope:** no existe ningún puerto de generación de imagen/video hoy; requiere investigación de factibilidad propia (modelo, costo de cómputo, formatos) antes de poder planearse.

---

**Descartado:** reemplazo/agregado de pista de audio en un video existente — evaluado, sin caso de uso claro con el negocio. Sin ID (nunca entró en desarrollo activo).
