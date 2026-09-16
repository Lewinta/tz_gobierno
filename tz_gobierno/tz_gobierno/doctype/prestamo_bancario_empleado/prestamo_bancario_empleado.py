# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Préstamo bancario al personal con la institución como garante.

NO se modela como un préstamo que otorga la institución. La app Lending de Frappe
asume que la propia empresa es la prestamista, y aquí no lo es: el banco presta, el
empleado debe, y la institución solo garantiza y descuenta la cuota por nómina. El
pasivo vive en el banco, no en el balance de la institución — modelarlo al revés
inflaría los pasivos del Estado de Situación Financiera con deuda ajena.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PrestamoBancarioEmpleado(Document):
	def validate(self):
		self.validar_cuotas()
		self.calcular_saldo()
		self.actualizar_estado()

	def validar_cuotas(self):
		if flt(self.cuota_mensual) <= 0:
			frappe.throw(_("La cuota mensual debe ser mayor que cero."))
		if int(self.numero_cuotas or 0) <= 0:
			frappe.throw(_("El número de cuotas debe ser mayor que cero."))
		if int(self.cuotas_pagadas or 0) > int(self.numero_cuotas):
			frappe.throw(
				_("Las cuotas pagadas ({0}) no pueden superar el total ({1}).").format(
					self.cuotas_pagadas, self.numero_cuotas
				)
			)

	def calcular_saldo(self):
		pendientes = int(self.numero_cuotas or 0) - int(self.cuotas_pagadas or 0)
		self.saldo_pendiente = max(pendientes, 0) * flt(self.cuota_mensual)

	def actualizar_estado(self):
		if self.estado == "Suspendido":
			return
		self.estado = "Saldado" if not flt(self.saldo_pendiente) else "Activo"

	def esta_vigente(self):
		return self.estado == "Activo" and int(self.cuotas_pagadas or 0) < int(
			self.numero_cuotas or 0
		)

	def registrar_cuota(self):
		"""Suma una cuota. La llama el hook de nómina cuando la deducción se aplica."""
		self.db_set("cuotas_pagadas", int(self.cuotas_pagadas or 0) + 1)
		self.reload()
		self.calcular_saldo()
		self.actualizar_estado()
		self.db_set("saldo_pendiente", self.saldo_pendiente)
		self.db_set("estado", self.estado)


def prestamos_vigentes(employee, company=None):
	filtros = {"employee": employee, "estado": "Activo"}
	if company:
		filtros["company"] = company

	vigentes = []
	for nombre in frappe.get_all("Prestamo Bancario Empleado", filters=filtros, pluck="name"):
		doc = frappe.get_doc("Prestamo Bancario Empleado", nombre)
		if doc.esta_vigente():
			vigentes.append(doc)
	return vigentes
