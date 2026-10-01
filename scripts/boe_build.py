#!/usr/bin/env python3
"""Construye los agregados del Radar del BOE a partir de raw/sumarios/*.xml.

Lee los sumarios XML cacheados (API de datos abiertos del BOE), extrae una fila
por disposición/anuncio y produce data/*.json con bloque meta por campo.

El sumario NO trae el rango normativo como campo: el tipo (ley, real decreto,
orden, resolución...) se deduce del inicio del título con reglas auditables
(TIPO_PATRONES, ordenadas por especificidad) en este mismo script. El tema se
clasifica con scripts/reglas_tema.json (palabras clave sobre título + epígrafe
+ departamento, primer tema que coincide según el orden del fichero).

Deduplicación: el identificador BOE-A-* es la clave; si reaparece se cuenta una
vez y se registra el duplicado. Las correcciones de errores son identificadores
nuevos: cuentan como disposición propia, etiquetadas con tipo propio.
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "raw" / "sumarios"
DATA = REPO / "data"
REGLAS = json.loads((REPO / "scripts" / "reglas_tema.json").read_text())

META_BASE = {
    "source": "API de datos abiertos BOE /datosabiertos/api/boe/sumario/{fecha}",
    "url": "https://www.boe.es/datosabiertos/api/api.php",
    "license": "Reutilización AEBOE (aviso legal www.boe.es)",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Tipo de disposición a partir del título (el sumario no trae campo "rango")
TIPO_PATRONES = [
    ("correccion de errores", r"^correccion de errores"),
    ("ley organica", r"^ley organica"),
    ("ley", r"^ley\s"),
    ("real decreto-ley", r"^real decreto-ley"),
    ("real decreto legislativo", r"^real decreto legislativo"),
    ("real decreto", r"^real decreto\s"),
    ("orden", r"^orden\s"),
    ("resolucion", r"^resolucion\s"),
    ("instruccion", r"^instruccion\s"),
    ("circular", r"^circular\s"),
    ("anuncio", r"^anuncio\s"),
    ("edicto", r"^edicto\s"),
    ("decreto-ley", r"^decreto-ley"),
    ("acuerdo", r"^acuerdo\s"),
    ("comunicado", r"^comunicado"),
    ("reglamento", r"^reglamento"),
    ("convenio", r"^convenio\s"),
    ("declaracion", r"^declaracion"),
]
def clasifica_tipo(titulo_norm: str) -> str:
    for nombre, pat in TIPO_PATRONES:
        if re.match(pat, titulo_norm):
            return nombre
    return "otro"


def clasifica_tema(campos_norm: str) -> str:
    for tema in REGLAS["orden"]:
        for pat in REGLAS["reglas"][tema]:
            # tipo "iva" dentro de "derivada" o "reta" dentro de "concreta"
            if re.search(r"(?<![\w])" + re.escape(pat.strip()) + r"(?![\w])", campos_norm):
                return tema
    return ""


def main() -> None:
    DATA.mkdir(exist_ok=True)
    archivos = sorted(RAW.glob("*.xml"))
    dias_sin_boe = sorted(p.stem for p in RAW.glob("*.404"))
    errores = sorted(p.stem for p in RAW.glob("*.err"))

    filas = []
    paginas_por_dia = {}
    duplicados = Counter()
    vistos = set()

    for f in archivos:
        dia = f.stem
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            errores.append(dia)
            continue
        paginas = {}
        for diario in root.iter("diario"):
            num = diario.get("numero")
            for sec in diario.findall("seccion"):
                sec_nombre = sec.get("nombre", "")
                sec_codigo = sec.get("codigo", "")
                for dep in sec.findall("departamento"):
                    dep_nombre = dep.get("nombre", "")
                    for epi in dep.findall("epigrafe"):
                        for item in epi.findall("item"):
                            filas.append((dia, num, sec_codigo, sec_nombre,
                                          dep_nombre, epi.get("nombre", ""), item))
                    for item in dep.findall("item"):
                        filas.append((dia, num, sec_codigo, sec_nombre,
                                      dep_nombre, "", item))
            # páginas: el BOE numera páginas de forma continua por año;
            # tomamos el máximo pagina_final de cada día como "páginas acumuladas"
            for item in diario.iter("item"):
                pdf = item.find("url_pdf")
                if pdf is not None and pdf.get("pagina_final"):
                    pf = int(pdf.get("pagina_final"))
                    paginas[(dia, num)] = max(paginas.get((dia, num), 0), pf)
        paginas_por_dia[dia] = max(paginas.values()) if paginas else None

    registros = []
    for (dia, num, sec_codigo, sec_nombre, dep, epi, item) in filas:
        ident = item.findtext("identificador", "")
        titulo = item.findtext("titulo", "")
        url_html = item.findtext("url_html", "")
        pdf = item.find("url_pdf")
        p_ini = int(pdf.get("pagina_inicial")) if pdf is not None and pdf.get("pagina_inicial") else None
        p_fin = int(pdf.get("pagina_final")) if pdf is not None and pdf.get("pagina_final") else None
        if ident in vistos:
            duplicados[ident] += 1
            continue
        vistos.add(ident)
        tnorm = norm(titulo)
        registros.append({
            "fecha": dia,
            "id": ident,
            "seccion": sec_nombre,
            "departamento": dep,
            "epigrafe": epi,
            "titulo": titulo,
            "tipo": clasifica_tipo(tnorm),
            "tema": clasifica_tema(norm(f"{titulo} {epi} {dep}")) or REGLAS.get("seccion_fallback", {}).get(sec_nombre, "sin_clasificar"),
            "pag_ini": p_ini,
            "pag_fin": p_fin,
            "url": url_html,
        })

    n = len(registros)
    correcciones = sum(1 for r in registros if r["tipo"] == "correccion de errores")

    por_dia = Counter(r["fecha"] for r in registros)
    media = n / max(len(por_dia), 1)
    dia_record, record = por_dia.most_common(1)[0]

    secciones = Counter(r["seccion"] for r in registros)
    departamentos = Counter(r["departamento"] for r in registros)
    tipos = Counter(r["tipo"] for r in registros)
    temas = Counter(r["tema"] for r in registros)
    sin_clasificar = temas.get("sin_clasificar", 0)

    pag_dia_valido = {d: p for d, p in paginas_por_dia.items() if p}
    paginas_anio = max(pag_dia_valido.values()) if pag_dia_valido else None

    autonomos = temas.get("autonomos_pymes", 0)

    meta = dict(META_BASE, period="2025-01-01 a 2025-12-31")
    out = {
        "meta": {
            "generado": date.today().isoformat(),
            **meta,
            "notas": [
                "Corte: año natural 2025 completo (elegido por ser el último año cerrado).",
                f"Días con BOE descargado: {len(archivos)}; días sin BOE (HTTP 404, domingos/festivos sin publicación): {len(dias_sin_boe)}; errores de descarga: {len(errores)}.",
                "No se descargó ningún PDF de disposición: el sumario XML trae título, sección, departamento, epígrafe y páginas.",
                f"Ítems con identificador duplicado dentro del corte (republish): {sum(duplicados.values())} (se cuenta 1 vez por id).",
                f"Correcciones de errores: {correcciones}. Son identificadores BOE-A nuevos: se cuentan como disposiciones propias, con tipo propio.",
                "El sumario no trae el rango normativo: el tipo se deduce del inicio del título (reglas auditables en scripts/boe_build.py).",
                "El tema se clasifica por palabras clave auditables en scripts/reglas_tema.json (primer tema que coincide según el orden del fichero).",
                "Un mismo asunto puede aparecer en días distintos (norma + corrección de errores + anuncios de desarrollo): el conteo es de documentos BOE, no de asuntos.",
            ],
        },
        "volumen": {
            "disposiciones_y_anuncios": {
                "valor": n, "unit": "documentos BOE (disposiciones y anuncios)",
                "source": meta["source"], "period": meta["period"], "url": meta["url"],
            },
            "dias_con_boe": len(archivos),
            "dias_sin_boe_404": len(dias_sin_boe),
            "errores": len(errores),
            "media_por_dia": {"valor": round(media, 1), "unit": "documentos/día (solo días con BOE)"},
            "dia_record": {"fecha": dia_record, "disposiciones": record},
            "paginas_anio_aprox": {"valor": paginas_anio, "unit": "páginas (máximo pagina_final acumulado del año)"},
            "correcciones_de_errores": correcciones,
            "duplicados_descartados": sum(duplicados.values()),
        },
        "por_seccion": secciones.most_common(),
        "por_departamento": departamentos.most_common(25),
        "por_tipo": tipos.most_common(),
        "por_tema": temas.most_common(),
        "sin_clasificar": {"valor": sin_clasificar, "pct": round(100 * sin_clasificar / n, 1)},
        "autonomos_pymes_total": autonomos,
        "dias": dict(sorted(por_dia.items())),
        "dias_sin_boe": dias_sin_boe,
    }
    (DATA / "boe_agregados.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2))

    serie = {
        "meta": {**meta, "unit": "documentos/día"},
        "dias": sorted(por_dia.items()),
    }
    (DATA / "boe_por_dia.json").write_text(
        json.dumps(serie, ensure_ascii=False, indent=2))

    cat = {
        "meta": {**meta, "unit": "1 fila por identificador BOE-A"},
        "disposiciones": registros,
    }
    (DATA / "boe_disposiciones.json").write_text(
        json.dumps(cat, ensure_ascii=False))

    # Catálogo ligero para la web: solo las normas de rango general (ley, real decreto-ley,
    # real decreto, orden ministerial, acuerdo y circular). El catálogo completo pesa decenas
    # de megas porque incluye los 75.000 anuncios y resoluciones, y no se puede servir desde
    # una página estática sin que tarde en cargar.
    #
    # Además se compacta: filas como arrays con un diccionario de órganos y de temas, y sin la
    # URL (se deriva del identificador, que es estable: /diario_boe/txt.php?id=<id>). Con los
    # objetos completos pesaba 2,1 MB; así queda en ~1,1 MB, que con gzip se sirve bien.
    RANGOS = ("ley", "decreto-ley", "real decreto", "orden", "acuerdo", "circular")
    normas = [r for r in registros if r["tipo"] in RANGOS]
    organos_l, temas_l = [], []
    oix, tix = {}, {}
    filas = []
    for r in normas:
        for campo, tabla, indice in ((r["departamento"], organos_l, oix), (r["tema"], temas_l, tix)):
            if campo not in indice:
                indice[campo] = len(tabla)
                tabla.append(campo)
        filas.append([r["fecha"], r["id"], r["tipo"], oix[r["departamento"]],
                      r["titulo"], r["epigrafe"] or "", tix[r["tema"]],
                      r["pag_ini"], r["pag_fin"]])
    (DATA / "boe_normas.json").write_text(json.dumps({
        "meta": {**meta, "unit": "1 fila por norma de rango general",
                 "note": f"{len(normas)} de {len(registros)} documentos: se han excluido anuncios, "
                         "resoluciones y actos de la Administración de Justicia",
                 "columnas": ["fecha", "id", "tipo", "organo_i", "titulo", "epigrafe", "tema_i",
                              "pag_ini", "pag_fin"],
                 "url": "https://www.boe.es/diario_boe/txt.php?id={id}"},
        "organos": organos_l, "temas": temas_l, "normas": filas}, ensure_ascii=False,
        separators=(",", ":")))

    sources = {
        "meta": {"source": "este fichero", "period": "-", "url": "-"},
        "fuentes": [
            {"nombre": "API datos abiertos BOE - sumario diario",
             "url": "https://boe.es/datosabiertos/api/boe/sumario/{AAAAMMDD}",
             "doc": "https://www.boe.es/datosabiertos/documentos/APIsumarioBOE.pdf",
             "formato": "XML/JSON", "uso": "descarga de sumarios", "periodo": "2025"},
            {"nombre": "Endpoint antiguo xml.php (disposiciones sueltas)",
             "url": "https://www.boe.es/diario_boe/xml.php?id=BOE-A-<id>",
             "nota": "funciona para BOE-A-*; para sumarios con id=BOE-S-<AAAAMMDD> devuelve 302 a errorParametros.php (medido)",
             "periodo": "-"},
            {"nombre": "Tablas auxiliares (departamentos, materias, rangos)",
             "url": "https://www.boe.es/datosabiertos/definitions/download_schema.php?id=datos-auxiliares-departamentos",
             "periodo": "-"},
        ],
    }
    (DATA / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2))

    print(f"registros={n} correcciones={correcciones} duplicados={sum(duplicados.values())} "
          f"sin_clasificar={sin_clasificar} ({100 * sin_clasificar / n:.1f}%) "
          f"dias_boe={len(archivos)} sin_boe={len(dias_sin_boe)} errores={len(errores)} paginas_max={paginas_anio}")
    print("record:", dia_record, record)
    print("secciones:", secciones.most_common())
    print("temas:", temas.most_common(10))


if __name__ == "__main__":
    main()
