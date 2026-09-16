# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Preparación de un sitio para contabilidad gubernamental.

El flujo normal de ERPNext siembra los masters básicos (grupos de artículo, UOMs,
grupos de suplidor, territorios…) desde el asistente de configuración inicial. Pero
ese asistente también crea una Company con el plan de cuentas estándar de ERPNext,
que es justo lo que no queremos: la institución usa el plan DIGECOG y nada más.

Este módulo siembra los masters sin pasar por el asistente, para poder montar el
sitio en el orden correcto: masters → Company sin CoA → plan DIGECOG.
"""

import frappe
from frappe.utils import nowdate

PAIS = "Dominican Republic"


def sembrar_masters(pais=PAIS):
	"""Crea los masters base de ERPNext sin crear ninguna Company.

	Idempotente por la vía barata: si ya hay Item Groups, se asume sembrado.
	"""
	if frappe.db.count("Item Group"):
		return False

	from erpnext.setup.setup_wizard.operations import install_fixtures

	install_fixtures.install(pais)
	frappe.db.commit()
	return True


def asegurar_fiscal_year(fecha=None):
	"""Crea el año fiscal del año calendario de `fecha` si no existe.

	El sector público dominicano usa año fiscal = año calendario (1 ene – 31 dic),
	así que no hay que preguntar por fechas de inicio.
	"""
	anio = (fecha or nowdate())[:4]
	if frappe.db.exists("Fiscal Year", anio):
		return anio

	doc = frappe.get_doc(
		{
			"doctype": "Fiscal Year",
			"year": anio,
			"year_start_date": f"{anio}-01-01",
			"year_end_date": f"{anio}-12-31",
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def preparar(pais=PAIS):
	"""Entrypoint: deja el sitio listo para crear instituciones e importar el plan."""
	sembrados = sembrar_masters(pais)
	fiscal_year = asegurar_fiscal_year()

	resumen = {
		"masters_sembrados": sembrados,
		"fiscal_year": fiscal_year,
		"item_groups": frappe.db.count("Item Group"),
		"uoms": frappe.db.count("UOM"),
		"supplier_groups": frappe.db.count("Supplier Group"),
	}
	print(resumen)
	return resumen
