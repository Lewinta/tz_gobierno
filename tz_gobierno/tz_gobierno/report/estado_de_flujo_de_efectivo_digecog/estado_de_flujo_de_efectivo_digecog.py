# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Estado de Flujo de Efectivo por método directo — DIGECOG no acepta el indirecto."""

import frappe
from frappe import _

from tz_gobierno.digecog import estados


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.company or not filters.from_date or not filters.to_date:
		return [], []

	filas, sin_clasificar = estados.flujo_efectivo(
		filters.company, filters.from_date, filters.to_date
	)

	if sin_clasificar:
		codigos = ", ".join(sorted({c for c, _m in sin_clasificar})[:10])
		frappe.msgprint(
			_(
				"Movimientos de caja con contrapartida sin clasificar: {0}. "
				"Se acumularon en «Otros» de operación para no descuadrar el estado; "
				"conviene mapearlos en digecog/mapeo.py."
			).format(codigos),
			title=_("Clasificación incompleta"),
			indicator="orange",
		)

	if not estados.cuadra_flujo_efectivo(filas):
		frappe.msgprint(
			_("El efectivo inicial más la variación no da el efectivo final."),
			title=_("El estado no cuadra"),
			indicator="red",
		)

	cols = [
		{"fieldname": "concepto", "label": _("Concepto"), "fieldtype": "Data", "width": 520},
		{"fieldname": "monto_actual", "label": _("Monto"), "fieldtype": "Currency", "width": 170},
	]
	return cols, filas
