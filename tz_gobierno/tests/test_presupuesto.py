# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Test del subledger presupuestario: compromiso → devengado → pagado (§4 del spec).

Es el módulo de mayor riesgo del pliego y lo que un perito probará en vivo en la
demo: crear una orden de compra que exceda el presupuesto y ver que el sistema la
rechaza. Por eso el ciclo se prueba completo, incluidas todas las reversiones.

La company de prueba se arma con un puñado de cuentas propias en vez de importar el
plan DIGECOG completo: importar 3,675 cuentas en cada corrida haría la suite
inusable, y el import ya tiene sus propios tests.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from tz_gobierno.digecog.coa_import import crear_company_sin_coa_estandar
from tz_gobierno.setup.sitio import asegurar_fiscal_year, sembrar_masters

COMPANY = "TZ Gob Test"
ABBR = "TGT"
PRESUPUESTO = 1000.0


def _cuenta(nombre, root_type, padre=None, is_group=0, account_type=None):
	docname = frappe.db.get_value(
		"Account", {"account_name": nombre, "company": COMPANY}, "name"
	)
	if docname:
		return docname

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"company": COMPANY,
			"account_name": nombre,
			"parent_account": padre,
			"is_group": is_group,
			"root_type": root_type,
			"account_type": account_type,
		}
	)
	doc.flags.ignore_permissions = True
	# parent_account es reqd en el doctype, así que una cuenta raíz solo se puede
	# crear saltando el mandatorio — igual que hace el import del plan DIGECOG.
	doc.flags.ignore_mandatory = True
	doc.insert()
	return doc.name


class TestPresupuesto(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.montar_institucion()
		frappe.db.commit()

	@classmethod
	def montar_institucion(cls):
		# El sitio puede no haber pasado por el asistente de ERPNext, así que los
		# masters base (item groups, UOMs, grupos de suplidor) se siembran aquí.
		sembrar_masters()
		crear_company_sin_coa_estandar(COMPANY, ABBR)

		gastos = _cuenta("Gastos Test", "Expense", is_group=1)
		cls.cuenta_gasto = _cuenta("Servicios Test", "Expense", padre=gastos)
		cls.cuenta_redondeo = _cuenta("Redondeo Test", "Expense", padre=gastos)

		pasivos = _cuenta("Pasivos Test", "Liability", is_group=1)
		cls.cuenta_pagar = _cuenta(
			"Proveedores Test", "Liability", padre=pasivos, account_type="Payable"
		)

		activos = _cuenta("Activos Test", "Asset", is_group=1)
		cls.cuenta_banco = _cuenta(
			"Banco Test", "Asset", padre=activos, account_type="Bank"
		)

		frappe.db.set_value(
			"Company",
			COMPANY,
			{
				"default_payable_account": cls.cuenta_pagar,
				"default_currency": "DOP",
				# ERPNext lo activa por defecto, y entonces exige una cuenta
				# "Stock Received But Not Billed" en cada factura de compra. Una
				# institución que compra servicios no lleva inventario perpetuo.
				"enable_perpetual_inventory": 0,
				"round_off_account": cls.cuenta_redondeo,
				"write_off_account": cls.cuenta_redondeo,
				"exchange_gain_loss_account": cls.cuenta_redondeo,
			},
		)

		cls.cost_center = cls.asegurar_cost_center()
		cls.fiscal_year = cls.asegurar_fiscal_year()
		cls.item = cls.asegurar_item()
		cls.supplier = cls.asegurar_supplier()

	@classmethod
	def asegurar_cost_center(cls):
		nombre = f"Main - {ABBR}"
		if frappe.db.exists("Cost Center", nombre):
			return nombre

		raiz = f"{COMPANY} - {ABBR}"
		if not frappe.db.exists("Cost Center", raiz):
			frappe.get_doc(
				{
					"doctype": "Cost Center",
					"cost_center_name": COMPANY,
					"company": COMPANY,
					"is_group": 1,
				}
			).insert(ignore_permissions=True)

		return frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": "Main",
				"parent_cost_center": raiz,
				"company": COMPANY,
				"is_group": 0,
			}
		).insert(ignore_permissions=True).name

	@classmethod
	def asegurar_fiscal_year(cls):
		from erpnext.accounts.utils import get_fiscal_year

		try:
			return get_fiscal_year(nowdate(), company=COMPANY, as_dict=True).name
		except Exception:
			anio = nowdate()[:4]
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
			return doc.name

	@classmethod
	def asegurar_item(cls):
		codigo = "SERVICIO-TEST-GOB"
		if frappe.db.exists("Item", codigo):
			return codigo
		return frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": codigo,
				"item_name": "Servicio de prueba",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True).name

	@classmethod
	def asegurar_supplier(cls):
		nombre = "Proveedor Test Gob"
		if frappe.db.exists("Supplier", nombre):
			return nombre
		return frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": nombre,
				"supplier_group": "All Supplier Groups",
			}
		).insert(ignore_permissions=True).name

	# ------------------------------------------------------------------ #

	def setUp(self):
		self.limpiar_subledger()
		self.linea = frappe.get_doc(
			{
				"doctype": "Linea Presupuestaria",
				"company": COMPANY,
				"fiscal_year": self.fiscal_year,
				"account": self.cuenta_gasto,
				"cost_center": self.cost_center,
				"monto_formulado": PRESUPUESTO,
				"monto_modificado": PRESUPUESTO,
			}
		).insert(ignore_permissions=True)

	def limpiar_subledger(self):
		"""Borra líneas y movimientos de la institución de prueba.

		No se confía en el rollback entre tests: la línea tiene una restricción de
		unicidad compuesta, así que cualquier resto de una corrida anterior haría
		fallar el setUp de todas las demás. Va por SQL directo para saltarse el
		on_trash que protege las líneas con movimientos.
		"""
		lineas = frappe.get_all(
			"Linea Presupuestaria", filters={"company": COMPANY}, pluck="name"
		)
		if lineas:
			frappe.db.delete("Movimiento Presupuestario", {"linea_presupuestaria": ["in", lineas]})
			frappe.db.delete("Linea Presupuestaria", {"name": ["in", lineas]})

	def recargar(self):
		self.linea.reload()
		return self.linea

	def crear_po(self, monto, submit=True):
		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": COMPANY,
				"supplier": self.supplier,
				"transaction_date": nowdate(),
				"schedule_date": add_days(nowdate(), 7),
				"currency": "DOP",
				"conversion_rate": 1,
				"items": [
					{
						"item_code": self.item,
						"qty": 1,
						"rate": monto,
						"schedule_date": add_days(nowdate(), 7),
						"expense_account": self.cuenta_gasto,
						"cost_center": self.cost_center,
					}
				],
			}
		)
		po.flags.ignore_permissions = True
		po.insert()
		if submit:
			po.submit()
		return po

	def facturar(self, po):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		pi = make_purchase_invoice(po.name)
		pi.credit_to = self.cuenta_pagar
		pi.posting_date = nowdate()
		for item in pi.items:
			item.expense_account = self.cuenta_gasto
			item.cost_center = self.cost_center
		pi.flags.ignore_permissions = True
		pi.insert()
		pi.submit()
		return pi

	def pagar(self, pi):
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		pe = get_payment_entry("Purchase Invoice", pi.name)
		pe.paid_from = self.cuenta_banco
		pe.reference_no = "TEST-PAGO"
		pe.reference_date = nowdate()
		pe.posting_date = nowdate()
		pe.flags.ignore_permissions = True
		pe.insert()
		pe.submit()
		return pe

	def assertSaldos(self, comprometido, devengado, pagado, disponible):
		lp = self.recargar()
		self.assertAlmostEqual(flt(lp.monto_comprometido), comprometido, places=2,
		                       msg="monto_comprometido")
		self.assertAlmostEqual(flt(lp.monto_devengado), devengado, places=2,
		                       msg="monto_devengado")
		self.assertAlmostEqual(flt(lp.monto_pagado), pagado, places=2, msg="monto_pagado")
		self.assertAlmostEqual(flt(lp.disponible), disponible, places=2, msg="disponible")

	# ------------------------------------------------------------------ #
	# Casos
	# ------------------------------------------------------------------ #

	def test_linea_nace_con_todo_disponible(self):
		self.assertSaldos(0, 0, 0, PRESUPUESTO)

	def test_orden_que_excede_el_presupuesto_es_rechazada(self):
		"""El control que el perito probará en la demo."""
		po = self.crear_po(1200, submit=False)
		with self.assertRaises(frappe.ValidationError):
			po.submit()
		self.assertSaldos(0, 0, 0, PRESUPUESTO)

	def test_orden_dentro_del_presupuesto_compromete(self):
		self.crear_po(800)
		self.assertSaldos(800, 0, 0, 200)

	def test_factura_transiciona_comprometido_a_devengado(self):
		po = self.crear_po(800)
		self.facturar(po)
		# El disponible no cambia: el dinero sigue gastado, solo cambió de etapa.
		self.assertSaldos(0, 800, 0, 200)

	def test_pago_transiciona_devengado_a_pagado(self):
		po = self.crear_po(800)
		pi = self.facturar(po)
		self.pagar(pi)
		self.assertSaldos(0, 0, 800, 200)

	def test_cancelar_orden_libera_el_compromiso(self):
		po = self.crear_po(800)
		self.assertSaldos(800, 0, 0, 200)
		po.cancel()
		self.assertSaldos(0, 0, 0, PRESUPUESTO)

	def test_cancelar_factura_restituye_el_compromiso_de_la_orden(self):
		"""Anular la factura no libera presupuesto: la orden sigue abierta.

		Si el compromiso no volviera, quedaría disponible un dinero que en realidad
		está comprometido por una orden viva, y la próxima orden podría gastarlo dos
		veces. Es el error clásico de los subledgers presupuestarios mal cerrados.
		"""
		po = self.crear_po(800)
		pi = self.facturar(po)
		self.assertSaldos(0, 800, 0, 200)

		pi.cancel()
		self.assertSaldos(800, 0, 0, 200)

	def test_cancelar_pago_retorna_a_devengado(self):
		po = self.crear_po(800)
		pi = self.facturar(po)
		pe = self.pagar(pi)
		pe.cancel()
		self.assertSaldos(0, 800, 0, 200)

	def test_ciclo_completo_y_reversion_total_deja_todo_en_cero(self):
		po = self.crear_po(800)
		pi = self.facturar(po)
		pe = self.pagar(pi)
		self.assertSaldos(0, 0, 800, 200)

		# Cada cancelación toca el documento de aguas arriba (el pago actualiza el
		# outstanding de la factura, la factura el per_billed de la orden), así que
		# hay que releer antes de cancelar o Frappe lanza TimestampMismatchError.
		pe.cancel()
		pi.reload()
		pi.cancel()
		po.reload()
		po.cancel()
		self.assertSaldos(0, 0, 0, PRESUPUESTO)

	def test_reversos_nunca_son_montos_negativos(self):
		"""El spec exige trazabilidad: reverso = fila propia con monto positivo."""
		po = self.crear_po(800)
		po.cancel()

		montos = frappe.get_all(
			"Movimiento Presupuestario",
			filters={"linea_presupuestaria": self.linea.name},
			pluck="monto",
		)
		self.assertTrue(montos)
		for monto in montos:
			self.assertGreater(flt(monto), 0)

	def test_no_se_puede_presupuestar_contra_cuenta_de_grupo(self):
		grupo = frappe.db.get_value("Account", self.cuenta_gasto, "parent_account")
		linea = frappe.get_doc(
			{
				"doctype": "Linea Presupuestaria",
				"company": COMPANY,
				"fiscal_year": self.fiscal_year,
				"account": grupo,
				"cost_center": self.cost_center,
				"monto_modificado": 500,
			}
		)
		with self.assertRaises(frappe.ValidationError):
			linea.insert(ignore_permissions=True)

	def test_no_se_permiten_dos_lineas_para_la_misma_combinacion(self):
		duplicada = frappe.get_doc(
			{
				"doctype": "Linea Presupuestaria",
				"company": COMPANY,
				"fiscal_year": self.fiscal_year,
				"account": self.cuenta_gasto,
				"cost_center": self.cost_center,
				"monto_modificado": 500,
			}
		)
		with self.assertRaises(frappe.ValidationError):
			duplicada.insert(ignore_permissions=True)
