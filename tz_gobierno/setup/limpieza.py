# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Purga de las instituciones que crea la suite de tests.

Los tests montan sus propias companies (`TZ Gob …`) porque necesitan un plan de
cuentas controlado y no pueden apoyarse en la institución de la demo. El efecto
secundario es que **correr los tests ensucia el sitio**: al terminar quedan cuatro o
cinco instituciones de juguete en el selector, justo lo que no quieres que vea un
perito en la demo.

No se limpian desde un tearDown porque los tests comparten la company entre clases y
borrarla al final de cada una multiplicaría el tiempo de la suite. Se limpia aquí,
como paso explícito antes de una demo:

    bench --site gob.tzcode.net execute tz_gobierno.setup.limpieza.eliminar_companies_de_prueba
"""

import frappe

PREFIJO_PRUEBA = "TZ Gob "

# Bajo ninguna circunstancia se toca la institución del pliego.
PROTEGIDAS = ("CES - Consejo Económico y Social",)


def companies_de_prueba():
	return [
		c
		for c in frappe.get_all("Company", pluck="name")
		if c.startswith(PREFIJO_PRUEBA) and c not in PROTEGIDAS
	]


def _borrar_company(company):
	frappe.flags.ignore_links = True

	# Los documentos confirmados hay que cancelarlos antes de poder borrarlos.
	for doctype in (
		"Payment Entry", "Purchase Invoice", "Purchase Order", "Journal Entry",
		"Salary Slip", "Payroll Entry", "Asset", "Salary Structure Assignment",
	):
		for nombre in frappe.get_all(doctype, filters={"company": company}, pluck="name"):
			doc = frappe.get_doc(doctype, nombre)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				doc.cancel()
			frappe.delete_doc(doctype, nombre, force=1, ignore_permissions=True)

	frappe.db.delete("GL Entry", {"company": company})

	for doctype in (
		"Movimiento Presupuestario", "Linea Presupuestaria", "Prestamo Bancario Empleado",
		"Banco Nomina Config", "Nota Estado Financiero", "Solicitud Tramite Pago",
		"Importacion SIAB", "Lote Tarjeta Credito",
	):
		campo = "company"
		if doctype == "Movimiento Presupuestario":
			continue  # cuelgan de la línea, que se borra arriba
		frappe.db.delete(doctype, {campo: company})

	for empleado in frappe.get_all("Employee", filters={"company": company}, pluck="name"):
		frappe.delete_doc("Employee", empleado, force=1, ignore_permissions=True)

	# Cuentas y centros de costo, de la hoja hacia la raíz.
	for doctype in ("Account", "Cost Center"):
		for nombre in frappe.get_all(
			doctype, filters={"company": company}, order_by="lft desc", pluck="name"
		):
			frappe.delete_doc(
				doctype, nombre, force=1, ignore_permissions=True, ignore_on_trash=True
			)

	frappe.delete_doc("Company", company, force=1, ignore_permissions=True,
	                  ignore_on_trash=True)


@frappe.whitelist()
def eliminar_companies_de_prueba():
	"""Borra las instituciones de juguete. Nunca toca la de la demo."""
	eliminadas = []

	for company in companies_de_prueba():
		_borrar_company(company)
		eliminadas.append(company)

	# Movimientos que quedaron sin línea presupuestaria tras la purga.
	frappe.db.sql(
		"""delete m from `tabMovimiento Presupuestario` m
		   left join `tabLinea Presupuestaria` l on l.name = m.linea_presupuestaria
		   where l.name is null"""
	)

	frappe.db.commit()

	return {
		"eliminadas": eliminadas,
		"restantes": frappe.get_all("Company", pluck="name"),
	}
