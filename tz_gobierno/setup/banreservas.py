# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Configuración de ejemplo de nómina bancaria para Banreservas.

IMPORTANTE: este layout **no está verificado con el banco**. Banreservas entrega el
formato del archivo directamente al cliente institucional y no lo publica. Las
columnas de abajo son las que típicamente pide un archivo de nómina dominicano, y el
registro se crea con `verificado = 0` para que el sistema advierta cada vez que
genere un archivo con él.

Cuando el CES consiga el layout real: editar el registro `Banreservas`, ajustar
posiciones/anchos y marcar `verificado`. No hay que tocar código.
"""

import frappe

BANCO = "Banreservas"

COLUMNAS_TENTATIVAS = [
	{"posicion": 1, "campo": "Cuenta bancaria del empleado", "ancho": 20, "relleno": "Derecha"},
	{"posicion": 2, "campo": "Cédula", "ancho": 11, "relleno": "Izquierda"},
	{"posicion": 3, "campo": "Nombre completo", "ancho": 40, "relleno": "Derecha"},
	{"posicion": 4, "campo": "Monto neto", "ancho": 15, "relleno": "Izquierda"},
]


def crear(company):
	"""Crea la config de ejemplo si no existe. Idempotente."""
	if frappe.db.exists("Banco Nomina Config", BANCO):
		return BANCO

	doc = frappe.get_doc(
		{
			"doctype": "Banco Nomina Config",
			"banco": BANCO,
			"company": company,
			"formato_archivo": "TXT ancho fijo",
			"extension": "txt",
			"verificado": 0,
			"columnas": COLUMNAS_TENTATIVAS,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.commit()
	return doc.name
