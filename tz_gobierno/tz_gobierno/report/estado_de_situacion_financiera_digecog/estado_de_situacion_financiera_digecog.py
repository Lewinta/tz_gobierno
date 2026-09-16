# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Estado de Situación Financiera (Balance General) en el formato oficial DIGECOG.

El layout es fijo: los rubros del modelo se imprimen siempre, tengan saldo o no.
La lógica vive en tz_gobierno.digecog.estados para poder probarla sin la UI.
"""

import frappe
from frappe import _

from tz_gobierno.digecog import estados


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.company or not filters.as_on_date:
		return [], []

	comparativo = bool(filters.get("mostrar_periodo_anterior"))
	filas, sin_mapear = estados.situacion_financiera(
		filters.company, filters.as_on_date, comparativo=comparativo
	)

	mensaje = None
	if sin_mapear:
		codigos = ", ".join(c for c, _m in sin_mapear[:10])
		mensaje = _(
			"Hay cuentas con saldo que ningún rubro del modelo cubre: {0}. "
			"El estado no cuadra hasta que se mapeen en digecog/mapeo.py."
		).format(codigos)
	elif not estados.cuadra_situacion_financiera(filas):
		mensaje = _("Total activos no coincide con Total pasivos + patrimonio.")

	if mensaje:
		frappe.msgprint(mensaje, title=_("Revisar"), indicator="orange")

	return columnas(comparativo), filas


def columnas(comparativo):
	cols = [
		{"fieldname": "concepto", "label": _("Concepto"), "fieldtype": "Data", "width": 420},
		{"fieldname": "monto_actual", "label": _("Período actual"), "fieldtype": "Currency",
		 "width": 170},
	]
	if comparativo:
		cols.append({"fieldname": "monto_anterior", "label": _("Período anterior"),
		             "fieldtype": "Currency", "width": 170})
	return cols
