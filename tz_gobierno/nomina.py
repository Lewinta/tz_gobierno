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


# --------------------------------------------------------------------------- #
# La nómina como ejecución presupuestaria
# --------------------------------------------------------------------------- #
"""
En una institución pública el sueldo es, normalmente, la mayor línea del
presupuesto: en el CES son 18 de 23.9 millones. Si la nómina no pasa por el
subledger, el Estado de Comparación de Importes Presupuestados y Realizados muestra
0% de ejecución en la línea más grande, que es un resultado sencillamente falso.

El §4.3 del spec solo engancha Purchase Order / Purchase Invoice / Payment Entry.
Esto lo completa por el lado del personal:

- El volante de pago **devenga** contra la línea presupuestaria de la cuenta de
  sueldos y el centro de costo del empleado.
- El pago de la corrida **liquida** ese devengado. Va como paso explícito y no
  adivinando cuál Journal Entry corresponde a qué nómina: ERPNext no deja enlace
  entre el asiento bancario y la corrida, y una heurística por monto y fecha se
  rompería el día que dos corridas coincidan.
"""


def _lineas_de_volante(slip):
	"""Mapea los devengos del volante a (línea presupuestaria, monto)."""
	from tz_gobierno.presupuesto import fiscal_year_de, resolver_linea

	centro = frappe.db.get_value("Employee", slip.employee, "payroll_cost_center")
	if not centro:
		return {}

	fiscal_year = fiscal_year_de(slip.end_date, slip.company)
	mapa = {}

	for devengo in slip.earnings:
		cuenta = frappe.db.get_value(
			"Salary Component Account",
			{"parent": devengo.salary_component, "company": slip.company},
			"account",
		)
		if not cuenta:
			continue

		linea = resolver_linea(slip.company, fiscal_year, cuenta, centro)
		if not linea:
			continue

		mapa[linea] = mapa.get(linea, 0.0) + flt(devengo.amount)

	return mapa


def registrar_devengado_nomina(doc, method=None):
	from tz_gobierno.presupuesto import ETAPA_DEVENGADO, _crear_movimiento, recalcular

	for linea, monto in _lineas_de_volante(doc).items():
		_crear_movimiento(
			linea, doc.end_date, ETAPA_DEVENGADO, monto, doc,
			observaciones=_("Devengo de nómina {0}").format(doc.name),
		)
		recalcular(linea)


def revertir_devengado_nomina(doc, method=None):
	from tz_gobierno.presupuesto import (
		ETAPA_DEVENGADO,
		ETAPA_REVERSADO,
		_crear_movimiento,
		_movimientos_vivos,
		recalcular,
	)

	for linea, monto in _movimientos_vivos(doc, ETAPA_DEVENGADO).items():
		_crear_movimiento(
			linea, doc.end_date, ETAPA_REVERSADO, monto, doc,
			etapa_revertida=ETAPA_DEVENGADO,
			observaciones=_("Reverso por cancelación de {0}").format(doc.name),
		)
		recalcular(linea)


@frappe.whitelist()
def registrar_pago_nomina(payroll_entry):
	"""Pasa de devengado a pagado la nómina de una corrida ya pagada al banco."""
	from tz_gobierno.presupuesto import (
		ETAPA_DEVENGADO,
		ETAPA_PAGADO,
		ETAPA_REVERSADO,
		_crear_movimiento,
		_movimientos_vivos_de,
		recalcular,
	)

	corrida = frappe.get_doc("Payroll Entry", payroll_entry)
	slips = frappe.get_all(
		"Salary Slip",
		filters={"payroll_entry": payroll_entry, "docstatus": 1},
		pluck="name",
	)

	movidos = 0
	for slip in slips:
		vivos = _movimientos_vivos_de("Salary Slip", slip, ETAPA_DEVENGADO)
		for linea, monto in vivos.items():
			referencia = frappe._dict(doctype="Salary Slip", name=slip)
			_crear_movimiento(
				linea, corrida.posting_date, ETAPA_REVERSADO, monto, referencia,
				etapa_revertida=ETAPA_DEVENGADO,
				observaciones=_("Transición a pagado por la corrida {0}").format(payroll_entry),
			)
			_crear_movimiento(linea, corrida.posting_date, ETAPA_PAGADO, monto, referencia)
			recalcular(linea)
			movidos += 1

	return {"volantes": len(slips), "lineas_afectadas": movidos}
