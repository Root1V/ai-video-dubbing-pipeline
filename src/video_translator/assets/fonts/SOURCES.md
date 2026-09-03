# Origen y licencia

Las 6 tipografías de esta carpeta se bajaron de [Google Fonts](https://fonts.google.com)
(repositorio [google/fonts](https://github.com/google/fonts)), licencia
**SIL Open Font License 1.1 (OFL)** -- uso y redistribución libres,
incluyendo uso comercial, sin exigir atribución obligatoria (a diferencia
del CC-BY de los emojis, ver `assets/emojis/SOURCES.md`).

`Montserrat-Regular.ttf` es una instancia estática (peso 400) generada a
partir de la fuente variable oficial con `fonttools varLib.instancer`, con
el nombre de familia interno corregido de "Montserrat Thin" a "Montserrat"
(bug de nombrado del instance por default de la fuente variable original
-- sin corregirlo, el selector de fuentes de libass no la encuentra y cae
a una fuente de reemplazo). El resto son las tipografías originales sin
modificar.

Se bundlean en el repo (en vez de depender de que estén instaladas en el
sistema) porque el filtro `ass` de ffmpeg acepta un parámetro `fontsdir`
que las encuentra sin instalación -- mismo criterio que los PNG de emoji
(ver RM-32): assets versionados, no estado de la máquina.

| Archivo | Tipografía | Uso sugerido |
|---|---|---|
| `BebasNeue-Regular.ttf` | Bebas Neue | Títulos de impacto, condensada bold |
| `Montserrat-Regular.ttf` | Montserrat | Geométrica limpia, display |
| `Poppins-Regular.otf` | Poppins | Geométrica redondeada, moderna |
| `Righteous-Regular.ttf` | Righteous | Display bold redondeada |
| `Pacifico-Regular.ttf` | Pacifico | Script/brush casual |
| `DancingScript-Regular.ttf` | Dancing Script | Cursiva elegante |
