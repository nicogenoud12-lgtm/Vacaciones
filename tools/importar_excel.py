#!/usr/bin/env python3
"""
Lee la planilla de vacaciones actual (GFI-VACACIONES_*.xlsx) y genera el JSON
inicial para la app: configuración y empleados con su saldo de arranque.

Uso:
    python3 -I tools/importar_excel.py RUTA.xlsx [--anio 2026] > seed.json

Criterio de saldo inicial (período --anio):
    arrastre = Pendiente del año anterior - Anticipo del año
    La planilla mezcla días hábiles y corridos, así que se pasan a hábiles
    con la equivalencia 7 corridos = 5 hábiles (redondeado). Cada empleado
    importado con saldo queda marcado para revisar.
"""
import argparse
import json
import re
import sys
import unicodedata

import openpyxl


def norm(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[^A-Z, ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def partes(nombre):
    """(apellido, primer nombre) normalizados. 'GARELLI ADRIAN' y 'GARELLI, ADRIÁN EDUARDO' -> ('GARELLI', 'ADRIAN')."""
    n = norm(nombre)
    if "," in n:
        ape, nom = n.split(",", 1)
    else:
        p = n.split(" ")
        ape, nom = p[0], " ".join(p[1:])
    nom = nom.strip().split(" ")[0] if nom.strip() else ""
    return ape.replace(" ", ""), nom


def misma_persona(a, b):
    """Mismo apellido y un primer nombre es abreviatura del otro (M. / MA. / MARIA)."""
    (a1, n1), (b1, n2) = partes(a), partes(b)
    return a1 == b1 and bool(n1) and bool(n2) and (n1.startswith(n2) or n2.startswith(n1))


def slug(nombre):
    n = norm(nombre).lower().replace(",", "")
    return re.sub(r"[^a-z0-9]+", "-", n).strip("-")[:60]


def titulo(nombre):
    """'ALFARO, AXEL LEONEL' -> 'Alfaro, Axel Leonel'."""
    nombre = re.sub(r"\s+", " ", str(nombre)).strip()
    return " ".join(p[:1].upper() + p[1:].lower() if p.isupper() or p.islower() else p for p in nombre.split(" "))


def a_habiles(dias):
    return int(round(dias * 5 / 7))


FERIADOS = {
    # 2026 (Decreto de feriados 2026; verificar puentes)
    "2026-01-01": "Año Nuevo",
    "2026-02-16": "Carnaval",
    "2026-02-17": "Carnaval",
    "2026-03-23": "Puente turístico",
    "2026-03-24": "Día de la Memoria",
    "2026-04-02": "Malvinas",
    "2026-04-03": "Viernes Santo",
    "2026-05-01": "Día del Trabajador",
    "2026-05-25": "Revolución de Mayo",
    "2026-06-15": "Paso a la Inmortalidad de Güemes (trasladado)",
    "2026-06-20": "Día de la Bandera",
    "2026-07-09": "Día de la Independencia",
    "2026-07-10": "Puente turístico",
    "2026-08-17": "San Martín",
    "2026-10-12": "Diversidad Cultural",
    "2026-11-23": "Soberanía Nacional (trasladado)",
    "2026-12-07": "Puente turístico",
    "2026-12-08": "Inmaculada Concepción",
    "2026-12-25": "Navidad",
    # 2027 (fijos y trasladables según la regla general; puentes aún no definidos)
    "2027-01-01": "Año Nuevo",
    "2027-02-08": "Carnaval",
    "2027-02-09": "Carnaval",
    "2027-03-24": "Día de la Memoria",
    "2027-03-26": "Viernes Santo",
    "2027-04-02": "Malvinas",
    "2027-05-01": "Día del Trabajador",
    "2027-05-25": "Revolución de Mayo",
    "2027-06-21": "Paso a la Inmortalidad de Güemes (trasladado)",
    "2027-06-20": "Día de la Bandera",
    "2027-07-09": "Día de la Independencia",
    "2027-08-16": "San Martín (trasladado)",
    "2027-10-11": "Diversidad Cultural (trasladado)",
    "2027-11-20": "Soberanía Nacional",
    "2027-12-08": "Inmaculada Concepción",
    "2027-12-25": "Navidad",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--anio", type=int, default=2026)
    ap.add_argument("--empresa", default="GFI", help="Sigla de la empresa de la planilla (GFI o AZ)")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.xlsx, data_only=True)
    ws = wb[str(args.anio)]

    # Encabezados en la fila 6: buscar columnas por nombre
    cols = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(6, c).value
        if isinstance(v, str):
            k = norm(v)
            if k == "INGRESO":
                cols["ingreso"] = c
            elif k == "APELLIDO Y NOMBRE":
                cols["nombre"] = c
            elif k.startswith("VAC") and "vac" not in cols:
                cols["vac"] = c
            elif k.startswith("PENDIENTE"):
                cols["pend"] = c
            elif k.startswith("ANTICIP") and "$" not in v and "antic" not in cols:
                cols["antic"] = c  # no confundir con "ANTICIPO $"
    falta = {"ingreso", "nombre", "pend", "antic"} - cols.keys()
    if falta:
        sys.exit(f"No encontré las columnas {falta} en la hoja {args.anio}")

    empleados = {}
    for r in range(7, ws.max_row + 1):
        nombre = ws.cell(r, cols["nombre"]).value
        ingreso = ws.cell(r, cols["ingreso"]).value
        if not nombre or not hasattr(ingreso, "strftime"):
            if nombre is None and r > 10 and all(ws.cell(r + i, cols["nombre"]).value is None for i in range(1, 3)):
                break  # fin de la tabla principal (abajo hay listas auxiliares)
            continue
        if "vac" in cols and ws.cell(r, cols["vac"]).value in (None, ""):
            continue  # sin días del año en la planilla: baja o fuera de la lista (ej. Caliva, Lira en Arazá)
        area = str(ws.cell(r, 1).value or "").strip().upper()
        pend = ws.cell(r, cols["pend"]).value or 0
        antic = ws.cell(r, cols["antic"]).value or 0
        pend = pend if isinstance(pend, (int, float)) else 0
        antic = antic if isinstance(antic, (int, float)) else 0
        arrastre = a_habiles(pend) - a_habiles(antic)
        notas = []
        if pend:
            notas.append(f"pendiente {args.anio - 1}: {pend:g} días → {a_habiles(pend)} háb.")
        if antic:
            notas.append(f"anticipo {args.anio}: {antic:g} días → {a_habiles(antic)} háb.")
        k = slug(nombre)
        empleados[k] = {
            "id": slug(nombre),
            "nombre": titulo(nombre),
            "ingreso": ingreso.strftime("%Y-%m-%d"),
            "empresa": args.empresa,
            "sector": "Administración" if area == "ADMIN" else "Planta",
            "convenio": "Comercio" if area == "ADMIN" else "Madera",
            "area": area or None,
            "activo": True,
            "baja": None,
            "inicio": {
                "anio": args.anio,
                "arrastre": arrastre,
                "origen": ("Excel " + "; ".join(notas)) if notas else "Excel: sin pendiente ni anticipo",
            },
            "revisar": bool(notas),
        }

    # Personal administrativo (GFI / AZ) — solo en la planilla de GFI
    if "VAC ADMIN 25" in wb.sheetnames:
        wa = wb["VAC ADMIN 25"]
        for r in range(7, wa.max_row + 1):
            emp, nombre = wa.cell(r, 1).value, wa.cell(r, 2).value
            if not nombre or emp not in ("GFI", "AZ"):
                continue
            igual = [e for e in empleados.values() if e["ingreso"] and misma_persona(e["nombre"], nombre)]
            if len(igual) > 1:
                sys.exit(f"'{nombre}' coincide con más de un empleado: {[e['nombre'] for e in igual]}")
            if igual:
                igual[0].update({"empresa": emp, "sector": "Administración", "convenio": "Comercio"})
                continue
            empleados[slug(nombre)] = {
                "id": slug(nombre),
                "nombre": titulo(nombre),
                "ingreso": None,
                "empresa": emp,
                "sector": "Administración",
                "convenio": "Comercio",
                "activo": True,
                "baja": None,
                "inicio": {"anio": args.anio, "arrastre": 0, "origen": "Excel VAC ADMIN: falta fecha de ingreso"},
                "revisar": True,
            }

    seed = {
        "config": {
            "periodoActivo": args.anio,
            "feriadosDescuentan": False,
            "feriados": [{"fecha": f, "nombre": n} for f, n in sorted(FERIADOS.items())],
            "localidad": "Pergamino",
            "empresas": {
                "GFI": "GENOUD FORESTO INDUSTRIAL S.A.",
                "AZ": "ARAZÁ S.A.C.I.F.E.",
            },
            "textoNota": (
                "Notificámosle que en cumplimiento a lo dispuesto por el artículo 154 de la Ley 20.744 "
                "comenzará el período de descanso anual que le corresponde, según se detalla a continuación."
            ),
        },
        "empleados": sorted(empleados.values(), key=lambda e: e["nombre"]),
    }
    ids = [e["id"] for e in seed["empleados"]]
    assert len(ids) == len(set(ids)), "ids duplicados"
    json.dump(seed, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
