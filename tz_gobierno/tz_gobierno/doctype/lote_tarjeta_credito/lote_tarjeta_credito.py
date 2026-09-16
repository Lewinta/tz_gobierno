# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LoteTarjetaCredito(Document):
	def validate(self):
		self.calcular_total()
		self.validar_cuentas()

	def calcular_total(self):
		self.monto_total = sum(flt(c.monto) for c in self.consumos)

	def validar_cuentas(self):
		"""Cada consumo va a una cuenta imputable; la tarjeta, a una de pasivo.

		Sin esto el asiento se genera contra cuentas de grupo y ERPNext lo rechaza al
		final, después de que el usuario cargó veinte consumos a mano.
		"""
		for consumo in self.consumos:
			if frappe.db.get_value("Account", consumo.account, "is_group"):
				frappe.throw(
					_("Fila {0}: {1} es una cuenta de grupo y no admite asientos.").format(
						consumo.idx, consumo.account
					)
				)

		if self.cuenta_tarjeta:
			cuenta = frappe.db.get_value(
				"Account", self.cuenta_tarjeta, ["is_group", "root_type"], as_dict=True
			)
			if cuenta.is_group:
				frappe.throw(_("La cuenta de la tarjeta no puede ser un grupo."))
			if cuenta.root_type != "Liability":
				frappe.throw(
					_("La cuenta de la tarjeta debe ser de pasivo; {0} es {1}.").format(
						self.cuenta_tarjeta, cuenta.root_type
					)
				)

	@frappe.whitelist()
	def generar_asiento(self):
		"""Crea el Journal Entry del lote: un débito por consumo, un crédito a la tarjeta.

		El asiento queda en borrador a propósito: quien concilia la tarjeta no es
		necesariamente quien aprueba el asiento.
		"""
		if self.journal_entry:
			frappe.throw(
				_("Este lote ya generó el asiento {0}.").format(self.journal_entry)
			)
		if not self.consumos:
			frappe.throw(_("El lote no tiene consumos."))

		asiento = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"company": self.company,
				"posting_date": self.fecha_corte,
				"user_remark": _("Consumos de tarjeta {0} ****{1}, período {2}").format(
					self.banco, self.ultimos_4_digitos, self.periodo
				),
				"accounts": [
					{
						"account": consumo.account,
						"cost_center": consumo.cost_center,
						"debit_in_account_currency": flt(consumo.monto),
						"user_remark": consumo.comercio,
					}
					for consumo in self.consumos
				]
				+ [
					{
						"account": self.cuenta_tarjeta,
						"credit_in_account_currency": flt(self.monto_total),
					}
				],
			}
		)
		asiento.flags.ignore_permissions = True
		asiento.insert()

		self.db_set("journal_entry", asiento.name)
		frappe.msgprint(
			_("Asiento {0} creado en borrador.").format(
				frappe.utils.get_link_to_form("Journal Entry", asiento.name)
			),
			indicator="green",
		)
		return asiento.name

	@frappe.whitelist()
	def marcar_conciliado(self):
		if not self.journal_entry:
			frappe.throw(_("Genere el asiento antes de conciliar el lote."))
		self.db_set("estado", "Conciliado")
		return self.estado
