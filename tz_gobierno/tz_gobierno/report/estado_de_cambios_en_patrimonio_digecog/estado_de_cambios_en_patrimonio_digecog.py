# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Estado de Cambios en el Activo Neto/Patrimonio.

Es una matriz: los componentes del patrimonio en columnas y los movimientos del
período en filas, con dos ciclos (ejercicio anterior y actual) como exige el modelo.
"""

import frappe
from frappe import _

from tz_gobierno.digecog import estados


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.company or not filters.fiscal_year:
		return [], []

	filas = estados.cambios_patrimonio(filters.company, filters.fiscal_year)

	cols = [
		{"fieldname": "concepto", "label": _("Concepto"), "fieldtype": "Data", "width": 330},
	]
	for clave, etiqueta, _prefijos in estados.COLUMNAS_PATRIMONIO:
		cols.append(
			{"fieldname": clave, "label": _(etiqueta), "fieldtype": "Currency", "width": 165}
		)
	cols.append(
		{"fieldname": "total", "label": _("Total Activos Netos/Patrimonio"),
		 "fieldtype": "Currency", "width": 200}
	)

	return cols, filas
