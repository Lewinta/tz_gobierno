# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Solicitud de Trámite de Pago (§8 del spec).

El formulario propio del CES es interno y no está publicado. Los campos de aquí se
basan en el formulario "Certificación de Trámite Correcto" de la Contraloría General
de la República, que sí es público y refleja qué datos maneja un trámite de pago
gubernamental dominicano.

El Print Format se arma con el Print Format Builder y no en HTML a mano, para que
cuando llegue el formulario real del CES sea un ajuste de campos y no una
reprogramación de última hora.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SolicitudTramitePago(Document):
	def validate(self):
		self.validar_monto()
		self.validar_disponibilidad_presupuestaria()

	def validar_monto(self):
		if flt(self.monto) <= 0:
			frappe.throw(_("El monto del trámite debe ser mayor que cero."))

	def validar_disponibilidad_presupuestaria(self):
		"""Avisa si el trámite excede lo disponible en su línea presupuestaria.

		Es advertencia y no bloqueo: la solicitud es el paso previo al compromiso, y en
		el sector público es normal tramitar mientras una modificación presupuestaria
		está en curso. El bloqueo duro va donde tiene que ir, en la orden de compra
		(ver tz_gobierno/presupuesto.py).
		"""
		if not self.linea_presupuestaria:
			return

		disponible = flt(
			frappe.db.get_value("Linea Presupuestaria", self.linea_presupuestaria, "disponible")
		)
		if flt(self.monto) > disponible:
			frappe.msgprint(
				_("El trámite ({0}) supera lo disponible en la línea {1} ({2}).").format(
					frappe.format_value(self.monto, "Currency"),
					self.linea_presupuestaria,
					frappe.format_value(disponible, "Currency"),
				),
				title=_("Disponibilidad insuficiente"),
				indicator="orange",
			)
