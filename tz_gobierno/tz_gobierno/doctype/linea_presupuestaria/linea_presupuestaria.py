# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LineaPresupuestaria(Document):
	def validate(self):
		self.validar_cuenta_imputable()
		self.validar_unicidad()
		self.calcular_disponible()

	def validar_cuenta_imputable(self):
		"""Una línea presupuestaria solo puede colgar de una cuenta imputable.

		DIGECOG exige imputar al nivel más bajo del plan; presupuestar contra un grupo
		permitiría registrar en una cuenta que nunca recibe asientos, y el reporte de
		ejecución no cuadraría nunca.
		"""
		cuenta = frappe.db.get_value(
			"Account", self.account, ["is_group", "root_type"], as_dict=True
		)
		if not cuenta:
			frappe.throw(_("La cuenta {0} no existe").format(self.account))

		if cuenta.is_group:
			frappe.throw(
				_("{0} es una cuenta de grupo. El presupuesto se formula contra cuentas "
				  "imputables del último nivel.").format(self.account)
			)

		if cuenta.root_type not in ("Expense", "Income"):
			frappe.throw(
				_("{0} es de tipo {1}. Una línea presupuestaria solo aplica a cuentas de "
				  "Gasto o Ingreso.").format(self.account, cuenta.root_type)
			)

	def validar_unicidad(self):
		"""Una sola línea por (institución, año, cuenta, centro de costo, proyecto).

		Frappe solo sabe imponer unicidad sobre un campo, así que la restricción
		compuesta que pide el spec se valida aquí.
		"""
		duplicada = frappe.db.get_value(
			"Linea Presupuestaria",
			{
				"company": self.company,
				"fiscal_year": self.fiscal_year,
				"account": self.account,
				"cost_center": self.cost_center,
				"project": self.project or ["in", ["", None]],
				"name": ["!=", self.name],
			},
		)
		if duplicada:
			frappe.throw(
				_("Ya existe la línea presupuestaria {0} para esa combinación de "
				  "institución, año fiscal, cuenta, centro de costo y proyecto.").format(duplicada)
			)

	def calcular_disponible(self):
		self.disponible = (
			flt(self.monto_modificado)
			- flt(self.monto_comprometido)
			- flt(self.monto_devengado)
			- flt(self.monto_pagado)
		)

	def on_trash(self):
		if frappe.db.exists("Movimiento Presupuestario", {"linea_presupuestaria": self.name}):
			frappe.throw(
				_("No se puede eliminar: la línea tiene movimientos presupuestarios "
				  "registrados. El ledger es la traza de auditoría.")
			)
