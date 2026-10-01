# Radar del BOE

Todo lo que publicó el **Boletín Oficial del Estado en 2025**, descargado de su API oficial de
datos abiertos y puesto en un buscador.

- **Web:** <https://pedri77.github.io/boe-radar/>
- **Vídeo:** episodio `cci-10` de la serie [«Construido con IA»](https://iacedemy.com/free/yt/construido-con-ia/) de IAcademy.
- **Plantilla para hacer el tuyo:** [observatorio-datos-plantilla](https://github.com/pedri77/observatorio-datos-plantilla).

## Lo primero que se aprende

El BOE publicó **75.405 documentos** en 2025, una media de **240,9 al día** y **181.331 páginas**.
Suena abrumador hasta que se mira de qué es cada cosa:

| Qué es | Documentos | % |
|---|---:|---:|
| Anuncios (otros anuncios oficiales, contratación del sector público, particulares) | 35.523 | 47,1 % |
| Administración de Justicia | 12.669 | 16,8 % |
| Otras disposiciones | 10.660 | 14,1 % |
| Oposiciones y concursos | 10.019 | 13,3 % |
| Nombramientos, situaciones e incidencias | 5.072 | 6,7 % |
| **Disposiciones generales (las normas)** | **1.258** | **1,7 %** |
| Tribunal Constitucional | 204 | 0,3 % |

Y contando por rango normativo, no por sección: **3.728 normas de rango general** —132 leyes,
46 reales decretos-ley, 1.246 reales decretos, 1.645 órdenes ministeriales, 642 acuerdos y
17 circulares—. **El 4,9 % del boletín.**

El día con más publicación fue un sábado, el **10 de mayo de 2025: 568 documentos**.

## Esto no es asesoría legal

Aquí se describe lo que publica el BOE. No se interpreta, no se resume el contenido de una norma y
no se dice qué te obliga a ti. Cada fila enlaza al texto oficial en `boe.es` para que lo leas tú.

## Cómo se obtiene el BOE (medido)

```
GET https://boe.es/datosabiertos/api/boe/sumario/{AAAAMMDD}     Accept: application/xml
```

- El endpoint antiguo `diario_boe/xml.php?id=BOE-S-<fecha>` **ya no sirve para sumarios**: devuelve
  `302 → errorParametros.php` (comprobado). Sí funciona para disposiciones sueltas con `id=BOE-A-…`.
- En 2025: **313 respuestas 200 y 52 respuestas 404** (domingos y festivos sin boletín). Cero errores.
- Sin límite de tasa observable: 365 peticiones en unos 4 minutos con una pausa de cortesía de 0,25 s.
- **No hace falta descargar ningún PDF**: el sumario XML ya trae título, sección, departamento,
  epígrafe y páginas.

## Reproducirlo

```bash
python3 scripts/boe_fetch.py     # descarga los sumarios del año a raw/ (cachea; 4 min la primera vez)
python3 scripts/boe_build.py     # agrega y escribe data/*.json (unos 30 s)
```

| Fichero | Contenido |
|---|---|
| `data/boe_agregados.json` | Volumen, reparto por sección, departamento, tipo y tema |
| `data/boe_por_dia.json` | Serie diaria: `[fecha, documentos]` |
| `data/boe_normas.json` | Las 3.728 normas de rango general, compactadas para la web (~1,2 MB) |
| `data/boe_disposiciones.json` | Catálogo completo de los 75.405 documentos (39 MB, **no versionado**) |
| `scripts/reglas_tema.json` | Las reglas de clasificación por tema, auditables |

`raw/` (54 MB de XML) y el catálogo completo no se versionan: `boe_fetch.py` los repone.

## Cómo se clasifica el tema

Con **reglas de palabras clave** sobre el título y el epígrafe, guardadas en
`scripts/reglas_tema.json` y versionadas para que cualquiera pueda auditarlas. No hay modelo ni caja
negra: si una norma está mal clasificada, se ve qué palabra la llevó ahí y se corrige la regla.

Las reglas usan límite de palabra. Sin eso, «iva» casaba dentro de otras palabras y «reta» dentro de
«secretaría»: falsos positivos detectados durante la construcción.

**3.877 documentos (5,1 %) quedan sin clasificar** y se muestran como tales. No se inventa una
categoría para rellenar el hueco.

## Trampas encontradas

- **Una corrección de errores es un identificador nuevo.** El BOE republica el texto corregido con
  otro número `BOE-A-…`. En 2025 hubo al menos 189 (son un mínimo: solo las que empiezan por
  «Corrección de errores»). Contarlas dos veces infla el volumen.
- **El sumario no trae el rango normativo.** «Real decreto» u «orden» se deducen leyendo el título.
  Funciona bien para las normas, pero deja un 27,5 % como «otro»: casi todo son anuncios de la
  sección IV (BOE-B) que empiezan por un topónimo.
- **Disposición no es anuncio.** La sección V son notificaciones, licitaciones y subastas; la IV,
  actos de la Administración de Justicia. Contar «documentos publicados» como si fueran normas
  nuevas exagera mucho lo que cambia.
- **La numeración BOE-B** (Administración de Justicia) no sigue el patrón BOE-A y un scraper que
  busque solo `BOE-A-` pierde 198 documentos en un solo día. Comprobado.
- **Las páginas son continuas** dentro del diario: se acumula el máximo de `pagina_final`, no se
  suman las longitudes de cada documento.
- **El BORME es otro boletín** y no está aquí: es el Boletín Oficial del Registro Mercantil.

## Verificación

- Recuento propio de los `<item>` del sumario frente a lo que muestra la web del BOE en **4 días**:
  53/53, 568/568, 308/308 y 312/312. Cuadra exacto, incluidos los 198 BOE-B del último día.
- `boe_fetch.py` reejecutado: usa la caché y no re-descarga.
- `boe_build.py` reejecutado: cifras idénticas.

## Fuente y licencia

Agencia Estatal Boletín Oficial del Estado, API de datos abiertos. Reutilización permitida según el
aviso legal de [boe.es](https://www.boe.es). Los agregados y la clasificación son de elaboración
propia; la AEBOE no participa ni avala esta reutilización.

Código bajo **MIT** (`LICENSE`).
