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

## RM-15 — Gestión de usuarios
**Why:** antes los usuarios solo se creaban por script (`create_admin.py`); no había forma de verlos, crearlos, cambiar su rol o desactivarlos desde la UI.
**Scope:** sección "Administración" en el menú (solo admin): listado, botón "Agregar usuario" (nombre/email/password/rol), cambio de rol y activar/desactivar inline. `GET/POST/PATCH /api/users`, todos protegidos con `require_admin`. Un admin no puede quitarse su propio rol ni desactivarse a sí mismo (bloqueado en backend y reflejado en la UI). Sigue sin auto-registro ni invitaciones por email — crear una cuenta requiere acceso admin, por diseño.
Commits: `11a3556`, `31a6b03`

## RM-16 — Columnas de ejecución en la tabla de proyectos
**Ya implementado** antes de esta sesión (dashboard M1-M6 / v1.2.0) — `ProjectsListPage` ya muestra "Duración" y "ID de ejecución" por fila.
Commit: `2d2f149`

## RM-17 — Selector de fuente de media: orden y validación de URL
**Why:** antes "Pegar URL" no bloqueaba el envío del formulario aunque la previsualización automática fallara — dejaba pasar URLs realmente rotas sin ningún aviso hasta que el pipeline fallaba recién al intentar descargar.
**Scope:** en doblaje/subtítulos/transcripción, tabs reordenados (Buscar en YouTube → Subir archivo → Pegar URL, YouTube es el tab por defecto). `MediaUrlPreview` ahora es también la validación real (reusa `GET /media/preview`, la misma extracción de yt-dlp que usaría la descarga) y reporta éxito/fallo al formulario; el botón de envío queda deshabilitado hasta validar, con un botón "Validar URL" para reintentar a mano si falla. Editar la URL resetea la validación de inmediato.
Commit: `f1b101e`

## RM-18 — Resumen con highlights en Transcripción
**Why:** pedido explícito para el servicio de transcripción; introdujo la primera capacidad de resumen vía LLM, reusable por RM-11.
**Scope:** toggle "incluir un resumen" (aditivo, no reemplaza la transcripción completa) en `NewTranscriptionProjectPage`. Nuevo puerto `Summarizer` (`application/interfaces.py`) separado de `Translator` — resumir texto libre no tiene el invariante "N líneas → N líneas" que necesita `translate_batch`. `OllamaTranslator`/`LlamaServerTranslator` ganaron `summarize()` reusando su transporte HTTP existente (`_call_llm`), sin cliente nuevo. Videos largos se resumen map-reduce (por fragmentos + resumen final) para cubrir todo el video, no solo el principio.
Commit: `e840cb4`

## RM-19 — Modo oscuro
**Why:** pedido explícito del usuario; usuarios distintos tienen preferencias distintas de tema, y el tema por defecto debe adaptarse sin acción manual.
**Scope:** paleta oscura en `index.css` (`.dark`, Tailwind ya traía `darkMode: 'class'`). Sin preferencia guardada, el tema inicial se elige por la hora del sistema (`lib/theme.ts::getSystemHourTheme` — 6:00 a 17:59 claro, resto oscuro; no es `prefers-color-scheme`, que refleja el tema del SO, no la hora). Botón toggle en `Topbar` (icono sol/luna sincronizado con el tema activo), que al usarse guarda una preferencia explícita en `localStorage` y ya no se recalcula por hora. Script inline en `index.html` aplica la clase `dark` antes de montar React para evitar flash del tema equivocado.
Commit: `7356015`

## RM-20 — Auditoría de diseño responsive
**Why:** se esperan usuarios conectándose desde iPad y celulares; el diseño no se ha validado fuera de desktop.
**Scope:** auditar dashboard, formularios de creación y detalle de proyecto en anchos de tablet/mobile; corregir donde el layout se rompa. No incluye una app nativa ni un rediseño mobile-first desde cero.

## RM-21 — Mensajes de error legibles del pipeline
**Why:** hoy `project.error_message` muestra el mensaje técnico crudo de la excepción tal cual (a veces legible, a veces un stack trace de Python) — un usuario no técnico no puede entender por qué falló ni qué hacer al respecto.
**Scope:** mapear los tipos de error conocidos del pipeline (conexión al LLM, formato de descarga, disco lleno, modelo no encontrado, etc.) a un mensaje corto con causa probable + acción sugerida, mostrado en el detalle del proyecto en vez del texto crudo; conservar el mensaje técnico original visible en un detalle expandible para debugging.

---

**Descartado:** reemplazo/agregado de pista de audio en un video existente — evaluado, sin caso de uso claro con el negocio. Sin ID (nunca entró en desarrollo activo).
