# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Estado de Comparación de los Importes Presupuestados y Realizados.

Consume el subledger presupuestario sobre **base de efectivo**: el ejecutado es el
monto pagado, no el devengado, porque así lo define el modelo de DIGECOG.
"""

import frappe
from frappe import _

from tz_gobierno.digecog import estados


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.company or not filters.fiscal_year:
		return [], []

	filas = estados.comparacion_presupuesto(filters.company, filters.fiscal_year)

	cols = [
		{"fieldname": "concepto", "label": _("Concepto"), "fieldtype": "Data", "width": 400},
		{"fieldname": "presupuesto_reformado", "label": _("Presupuesto Reformado (A)"),
		 "fieldtype": "Currency", "width": 190},
		{"fieldname": "presupuesto_ejecutado", "label": _("Presupuesto Ejecutado (B)"),
		 "fieldtype": "Currency", "width": 190},
		{"fieldname": "porcentaje_ejecucion", "label": _("% de Ejecución (C=B/A)"),
		 "fieldtype": "Percent", "width": 160},
		{"fieldname": "variacion", "label": _("Variación (D=A-B)"),
		 "fieldtype": "Currency", "width": 170},
	]

	return cols, filas
