# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Notas a los Estados Financieros (§5.6 del spec).

El manual de DIGECOG exige seis notas obligatorias. El reporte las lista en el orden
definido y señala cuáles faltan, porque presentar los estados sin alguna de las seis
es una no conformidad de formato.
"""

import frappe
from frappe import _

NOTAS_OBLIGATORIAS = [
	"Entidad económica",
	"Base de presentación",
	"Moneda funcional y de presentación",
	"Uso de estimados y juicios",
	"Base de medición",
	"Resumen de políticas contables",
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.company or not filters.fiscal_year:
		return [], []

	notas = frappe.get_all(
		"Nota Estado Financiero",
		filters={"company": filters.company, "fiscal_year": filters.fiscal_year},
		fields=["name", "tipo", "orden", "contenido"],
		order_by="orden asc, tipo asc",
	)

	presentes = {n.tipo for n in notas}
	faltantes = [t for t in NOTAS_OBLIGATORIAS if t not in presentes]
	if faltantes:
		frappe.msgprint(
			_("Faltan notas obligatorias del manual de DIGECOG: {0}").format(
				", ".join(faltantes)
			),
			title=_("Juego de notas incompleto"),
			indicator="orange",
		)

	columnas = [
		{"fieldname": "orden", "label": _("Orden"), "fieldtype": "Int", "width": 70},
		{"fieldname": "tipo", "label": _("Nota"), "fieldtype": "Data", "width": 280},
		{"fieldname": "name", "label": _("Documento"), "fieldtype": "Link",
		 "options": "Nota Estado Financiero", "width": 170},
		{"fieldname": "contenido", "label": _("Contenido"), "fieldtype": "Text Editor",
		 "width": 600},
	]

	return columnas, notas
