# Radar del BOE — informe de datos (episodio cci-10)

Corte: **año natural 2025 completo** (2025-01-01 a 2025-12-31). Elegido por ser el último año cerrado y manejable: 365 días, 313 peticiones de sumario con contenido, ~230 KB/día, 4 minutos de descarga con pausa de 0,25 s. Reejecutable sin re-descargar (caché en `raw/sumarios/`).

## Cómo se obtiene el BOE de verdad (medido)

- Punto de entrada real y documentado (APIsumarioBOE.pdf, AEBOE, 28/06/2024):
  `GET https://boe.es/datosabiertos/api/boe/sumario/{AAAAMMDD}` con cabecera `Accept: application/xml`.
- El endpoint antiguo `https://www.boe.es/diario_boe/xml.php?id=BOE-S-<AAAAMMDD>` **ya no funciona para sumarios**: devuelve `302 → /error/errorParametros.php` (medido, también con User-Agent de navegador). Sí funciona para disposiciones sueltas (`id=BOE-A-2020-1` → 200, XML de 42 KB).
- Respuestas medidas: `200` (sumario XML), `404` (día sin BOE: domingos y festivos sin publicación). En todo 2025: 313×200, 52×404, 0 errores de red.
- Límite de tasa: **ninguno documentado**; descargamos 365 peticiones en ~4 min con pausa de cortesía de 0,25 s, sin un solo 429 ni corte.
- Formo del XML: `response > data > sumario > metadatos + diario(numero) > seccion > departamento > epigrafe > item(identificador, titulo, url_pdf con pagina_inicial/pagina_final/szBytes, url_html, url_xml)`.
- Alternativas consideradas: legislación consolidada de la misma API (por disposición, no por día, no sirve para volumen diario); datos.gob.es no ofrece volcados masivos del BOE mejores que esta API.

## Números medidos (2025)

| Métrica | Valor |
|---|---|
| Documentos BOE publicados (disposiciones + anuncios) | **75.405** |
| Días con BOE / sin BOE (404) | 313 / 52 |
| Media por día con BOE | **240,9** |
| Día récord | **sábado 10/05/2025: 568** (249 anuncios oficiales, 209 Administración de Justicia) |
| Páginas acumuladas del año (máx. pagina_final observado) | **181.331** |
| Sección I. Disposiciones generales (normas con rango) | **1.258** |
| Leyes (incluye orgánicas y de cualquier origen) | 198 (132 «Ley», 46 «decreto-ley», resto variantes) |
| Correcciones de errores (títulos que empiezan así) | 189 |
| Documentos con identificador duplicado en el año | 0 |

## Reparto por sección (2025)

- V. Anuncios — B. Otros anuncios oficiales: 19.965
- V. Anuncios — A. Contratación del Sector Público: 14.995
- IV. Administración de Justicia: 12.669
- III. Otras disposiciones: 10.660
- II. Autoridades y personal — B. Oposiciones y concursos: 10.019
- II. Autoridades y personal — A. Nombramientos: 5.072
- I. Disposiciones generales: 1.258
- V. Anuncios — C. Anuncios particulares: 563
- T.C. Tribunal Constitucional: 204

Gancho: de 75.405 documentos, solo 1.258 (1,7 %) son disposiciones generales; el 98 % son anuncios y administración.

## Temas (clasificación auditable en `scripts/reglas_tema.json`)

Top: justicia 16.121 · empleo/Seguridad Social 11.052 · medio ambiente/agua 8.766 · educación 7.594 · fiscal/tributos 7.257 · defensa y seguridad 5.020 · **autónomos y pymes 3.185 (4,2 % del total)** · sin clasificar 3.877 (5,1 %).

Método: palabras clave (coincidencia por palabra completa, sin tildes) sobre título + epígrafe + departamento, primer tema que coincide según el orden del fichero; si nada coincide, la sección IV y T.C. se asignan a justicia (fallback declarado). Se corrigió expresamente el falso positivo de subcadenas («iva» dentro de «derivada», «reta» dentro de «concreta»): la primera versión sin fronteras de palabra daba fiscal 60 %; con palabra completa, 9,6 %.

## Verificación manual (5 días contra la web del BOE)

Contando identificadores únicos BOE-A y BOE-B en la página de cada día (`www.boe.es/boe/dias/{yyyy}/{mm}/{dd}/`):

| Día | Nuestro | Web BOE | Idénticos |
|---|---|---|---|
| 01/01/2025 | 53 | 53 | ✓ |
| 10/05/2025 (récord) | 568 | 568 | ✓ |
| 30/06/2025 | 308 | 308 | ✓ |
| 15/09/2025 | 312 | 312 | ✓ |
| (15/09/2025 solapamiento) | 114 BOE-A web ⊂ 114 nuestros | ✓ | sin residuo en ningún sentido |

## Descartes y por qué

- 52 días devolvieron 404 (sin BOE): no se descartan, se listan en `data/boe_agregados.json → dias_sin_boe`.
- 0 descartes por error de red o XML corrupto.
- 0 duplicados por identificador dentro del corte.

## Trampas documentadas

1. **BOE-B**: la sección IV (Administración de Justicia) usa identificadores `BOE-B-*` (198 solo el 15/09/2025). Un scraper que solo busque `BOE-A` pierde ~17 % del volumen.
2. **Correcciones de errores**: son identificadores nuevos, no reemplazos; contamos 189 con título que *empieza* por «Corrección de errores», pero las que empiezan por «Resolución de … corrección de errores» quedan bajo «resolución»: es un mínimo medido, no el total real.
3. **Disposición ≠ anuncio**: la sección I (normas) es el 1,7 %; el volumen lo hacen anuncios, oposiciones y edictos judiciales. Mezclar ambos sin decirlo infla cualquier titular.
4. **Domingos/festivos**: 52 días sin BOE en 2025 (404 de la API); la media diaria 240,9 se calcula solo sobre días con BOE (sobre 365 sería 206,6).
5. **Diario extraordinario**: la API permite varios nodos `diario` por sumario (etiqueta `L`/extraordinario); no se observó ninguno en 2025, pero el parser lo soporta.
6. **El sumario no trae el rango normativo** (ley, RD, orden…): el «tipo» se deduce del inicio del título con regex auditables en `scripts/boe_build.py`; 20.743 ítems (27,5 %, casi todos BOE-B de juzgados que empiezan por topónimo) quedan como «otro».
7. **Numeración de páginas**: continua dentro del año y viene por ítem (`pagina_inicial/final`); el total 181.331 es el máximo `pagina_final` observado, no una suma.
8. **BORME**: diario aparte (`/diario_borme/`), no incluido.

## Ficheros

- `scripts/boe_fetch.py` — descarga cacheada (`raw/sumarios/AAAAMMDD.xml`, `.404`).
- `scripts/boe_build.py` — parseo, tipos, deduplicación, agregados.
- `scripts/reglas_tema.json` — reglas temáticas auditables (versionable).
- `data/boe_agregados.json`, `data/boe_por_dia.json`, `data/boe_disposiciones.json`, `data/sources.json`.
- `raw/` — 313 XML de sumario (~72 MB), no versionar.

Fuente: API de datos abiertos del BOE (AEBOE), reutilización permitida conforme a su aviso legal. Esto no es asesoría legal: se describe lo publicado, sin interpretación jurídica.
