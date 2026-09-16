# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Enganche de los préstamos bancarios del personal al ciclo de nómina (§7).

La institución es garante del préstamo, no prestamista: lo único que hace en nómina
es retener la cuota y remitirla al banco. Por eso el descuento se aplica como una
deducción normal del Salary Slip y no como una amortización de la app Lending.
"""

import frappe
from frappe import _
from frappe.utils import flt

from tz_gobierno.tz_gobierno.doctype.prestamo_bancario_empleado.prestamo_bancario_empleado import (
	prestamos_vigentes,
)

COMPONENTE_POR_DEFECTO = "Préstamo Bancario (garantía institucional)"


def aplicar_deducciones_de_prestamos(doc, method=None):
	"""Agrega al Salary Slip la cuota de cada préstamo vigente del empleado.

	Se engancha en `validate` para que el empleado vea el descuento en la vista previa
	de su volante, no solo al confirmarlo.
	"""
	if not doc.employee:
		return

	for prestamo in prestamos_vigentes(doc.employee, doc.company):
		componente = prestamo.salary_component or asegurar_componente()

		if _ya_tiene_componente(doc, componente):
			continue

		doc.append(
			"deductions",
			{
				"salary_component": componente,
				"amount": flt(prestamo.cuota_mensual),
				"default_amount": flt(prestamo.cuota_mensual),
			},
		)


def _ya_tiene_componente(doc, componente):
	return any(d.salary_component == componente for d in (doc.get("deductions") or []))


def registrar_cuotas_pagadas(doc, method=None):
	"""Al confirmar el volante, avanza el contador de cuotas de cada préstamo.

	Va en `on_submit` y no en `validate` porque una cuota solo cuenta como pagada
	cuando la nómina se confirma; si se revisa el borrador tres veces, el contador no
	debe avanzar tres veces.
	"""
	if not doc.employee:
		return

	for prestamo in prestamos_vigentes(doc.employee, doc.company):
		componente = prestamo.salary_component or COMPONENTE_POR_DEFECTO
		if _ya_tiene_componente(doc, componente):
			prestamo.registrar_cuota()


def revertir_cuotas_pagadas(doc, method=None):
	"""Al cancelar el volante, devuelve el contador de cuotas."""
	if not doc.employee:
		return

	nombres = frappe.get_all(
		"Prestamo Bancario Empleado",
		filters={"employee": doc.employee, "company": doc.company},
		pluck="name",
	)
	for nombre in nombres:
		prestamo = frappe.get_doc("Prestamo Bancario Empleado", nombre)
		componente = prestamo.salary_component or COMPONENTE_POR_DEFECTO
		if _ya_tiene_componente(doc, componente) and int(prestamo.cuotas_pagadas or 0) > 0:
			prestamo.db_set("cuotas_pagadas", int(prestamo.cuotas_pagadas) - 1)
			prestamo.reload()
			prestamo.calcular_saldo()
			prestamo.actualizar_estado()
			prestamo.db_set("saldo_pendiente", prestamo.saldo_pendiente)
			prestamo.db_set("estado", prestamo.estado)


def asegurar_componente():
	"""Crea el Salary Component de deducción si la institución no definió uno."""
	if frappe.db.exists("Salary Component", COMPONENTE_POR_DEFECTO):
		return COMPONENTE_POR_DEFECTO

	doc = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": COMPONENTE_POR_DEFECTO,
			"salary_component_abbr": "PBG",
			"type": "Deduction",
			"description": _(
				"Retención de la cuota de un préstamo bancario del empleado que la "
				"institución garantiza y descuenta por nómina."
			),
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name
