# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Validación de RNC de suplidores (§7 del spec).

SOBRE LA CONSULTA EN LÍNEA
--------------------------
El spec pide confirmar si la DGII expone un servicio web público de consulta de
estado de RNC **antes** de implementar, y no inventar uno si no existe. No se
encontró un endpoint público y documentado: el portal de la DGII ofrece consulta por
formulario web, no una API con contrato estable, y raspar ese formulario sería frágil
y además incompatible con el uso off-line que especifica el pliego.

Así que aquí solo va lo que se puede sostener:

1. Validación **estructural** del RNC/cédula, que sí es determinista y no depende de
   ningún servicio: longitud y dígito verificador.
2. Un campo `rnc_verificado` + `fecha_verificacion` para dejar constancia de la
   comprobación manual contra el portal de la DGII.

PENDIENTE: TZCode mantiene un directorio de RNC cargado desde los archivos de la
DGII en otro sitio del bench. Conectar esta validación contra ese directorio daría
verificación real sin depender de internet — es la vía natural, pero requiere decidir
cómo se replica el directorio a la institución. Ver [[project-rnc-directory]].
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.utils import nowdate

# Pesos del dígito verificador de RNC (9 dígitos, personas jurídicas).
PESOS_RNC = (7, 9, 8, 6, 5, 4, 3, 2)
# Pesos de la cédula dominicana (11 dígitos, personas físicas).
PESOS_CEDULA = (1, 2, 1, 2, 1, 2, 1, 2, 1, 2)


def solo_digitos(valor):
	return "".join(c for c in str(valor or "") if c.isdigit())


def rnc_valido(valor):
	"""Valida el dígito verificador de un RNC de 9 dígitos."""
	digitos = solo_digitos(valor)
	if len(digitos) != 9:
		return False

	suma = sum(int(d) * p for d, p in zip(digitos[:8], PESOS_RNC))
	resto = suma % 11

	if resto == 0:
		esperado = 2
	elif resto == 1:
		esperado = 1
	else:
		esperado = 11 - resto

	return int(digitos[8]) == esperado


def cedula_valida(valor):
	"""Valida el dígito verificador de una cédula de 11 dígitos (módulo 10)."""
	digitos = solo_digitos(valor)
	if len(digitos) != 11:
		return False

	suma = 0
	for digito, peso in zip(digitos[:10], PESOS_CEDULA):
		producto = int(digito) * peso
		suma += producto if producto < 10 else producto - 9

	return int(digitos[10]) == (10 - suma % 10) % 10


def identificacion_valida(valor):
	"""True si es un RNC o una cédula estructuralmente válidos."""
	digitos = solo_digitos(valor)
	if len(digitos) == 9:
		return rnc_valido(digitos)
	if len(digitos) == 11:
		return cedula_valida(digitos)
	return False


def asegurar_campos_supplier():
	"""Campos de constancia de la verificación manual del RNC."""
	creados = []
	campos = [
		{
			"fieldname": "rnc_verificado",
			"label": "RNC Verificado en DGII",
			"fieldtype": "Check",
			"insert_after": "tax_id",
			"description": "Marcar tras comprobar el estado del RNC en el portal de la "
			"DGII. No hay servicio web público que permita automatizarlo.",
		},
		{
			"fieldname": "fecha_verificacion_rnc",
			"label": "Fecha de Verificación",
			"fieldtype": "Date",
			"insert_after": "rnc_verificado",
			"read_only": 1,
			"depends_on": "rnc_verificado",
		},
	]

	for campo in campos:
		if frappe.db.exists("Custom Field", {"dt": "Supplier", "fieldname": campo["fieldname"]}):
			continue
		create_custom_field("Supplier", campo)
		creados.append(campo["fieldname"])

	return creados


def validar_supplier(doc, method=None):
	"""Valida la estructura del RNC del suplidor y sella la fecha de verificación."""
	if doc.tax_id and not identificacion_valida(doc.tax_id):
		frappe.throw(
			_(
				"El RNC/cédula «{0}» no es estructuralmente válido: el dígito "
				"verificador no corresponde."
			).format(doc.tax_id)
		)

	if doc.get("rnc_verificado") and not doc.get("fecha_verificacion_rnc"):
		doc.fecha_verificacion_rnc = nowdate()
	elif not doc.get("rnc_verificado"):
		doc.fecha_verificacion_rnc = None


def instalar():
	creados = asegurar_campos_supplier()
	if creados:
		frappe.db.commit()
	return creados
