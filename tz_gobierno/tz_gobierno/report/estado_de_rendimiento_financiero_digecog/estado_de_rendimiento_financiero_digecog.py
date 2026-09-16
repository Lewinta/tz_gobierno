# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Estado de Rendimiento Financiero (Ahorro/Desahorro) en el formato oficial DIGECOG."""

import frappe
from frappe import _

from tz_gobierno.digecog import estados


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.company or not filters.from_date or not filters.to_date:
		return [], []

	comparativo = bool(filters.get("mostrar_periodo_anterior"))
	filas, sin_mapear = estados.rendimiento_financiero(
		filters.company, filters.from_date, filters.to_date, comparativo=comparativo
	)

	if sin_mapear:
		codigos = ", ".join(c for c, _m in sin_mapear[:10])
		frappe.msgprint(
			_("Cuentas de resultado con saldo fuera del modelo: {0}").format(codigos),
			title=_("Revisar"),
			indicator="orange",
		)

	cols = [
		{"fieldname": "concepto", "label": _("Concepto"), "fieldtype": "Data", "width": 420},
		{"fieldname": "monto_actual", "label": _("Período actual"), "fieldtype": "Currency",
		 "width": 170},
	]
	if comparativo:
		cols.append({"fieldname": "monto_anterior", "label": _("Período anterior"),
		             "fieldtype": "Currency", "width": 170})

	return cols, filas
