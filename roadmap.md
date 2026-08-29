# Roadmap — Prosodia

Índice. Detalle de cada item en [docs/roadmap.md](docs/roadmap.md).

| # | Feature | Status | Description |
|---|---------|--------|-------------|
| RM-01 | Transcripción standalone | done | Subir audio/video y obtener transcripción sin traducir ni doblar. |
| RM-02 | TTS standalone | done | Texto → audio, con voz pública o propia. |
| RM-03 | Analítica de negocio | done | Stats reales en el dashboard, sobreviven al borrado del proyecto. |
| RM-04 | Página de subtítulos | done | Formulario de creación real para el servicio de subtítulos. |
| RM-05 | Previsualización de media | done | Reproductor de video/audio inline antes de descargar. |
| RM-06 | Waveform reactivo en vivo | done | Animación de ondas que reacciona al audio real. |
| RM-07 | Importar proyecto desde URL | done | Subir archivo, pegar URL, o buscar en YouTube dentro de la app. |
| RM-08 | Atribución correcta de fallos de etapa | done | La UI señala la etapa real que falló, no la siguiente. |
| RM-09 | Librería de voces persistente | todo | Guardar y reusar voces clonadas entre proyectos. |
| RM-10 | Plantillas reutilizables | todo | Guardar config de un proyecto como plantilla nombrada. |
| RM-11 | Documento → audio narrado | todo | Resumir un documento y narrarlo con TTS. |
| RM-12 | API para desarrolladores | todo | Auth por API key + rate limiting para uso externo. |
| RM-13 | Workspace multi-usuario + facturación | todo | Equipos con varios usuarios y billing. |
| RM-14 | Imagen+texto → micro-video social | done | Video vertical narrado (Ken Burns + captions) desde una imagen y un texto. |
| RM-15 | Gestión de usuarios | done | Sección en el menú para administrar usuarios y su rol. |
| RM-16 | Columnas de ejecución en la tabla de proyectos | done | Agregar ID de ejecución y duración total al listado. |
| RM-17 | Selector de fuente de media: orden y validación de URL | done | YouTube primero; validar URL antes de habilitar el envío si falla el preview. |
| RM-18 | Resumen con highlights en Transcripción | done | Toggle opcional: además de la transcripción completa, un resumen de puntos clave. |
| RM-19 | Modo oscuro | done | Detecta claro/oscuro por la hora del sistema; botón para alternar a demanda. |
| RM-20 | Auditoría de diseño responsive | todo | Revisar y corregir el diseño para tablet/celular. |
| RM-21 | Mensajes de error legibles del pipeline | todo | Traducir el error técnico de una etapa fallida a una causa probable entendible. |
| RM-22 | Micro-video con video generado por IA | todo | Alternativa a RM-14 con un modelo de video generativo en vez de composición ffmpeg. |
