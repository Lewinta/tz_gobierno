# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Tests de los Estados Financieros DIGECOG (§5 del spec).

Se monta una institución con un puñado de cuentas de **códigos DIGECOG reales** (no
inventados) y tres asientos sencillos cuyo resultado se puede verificar a mano. Sobre
eso se comprueban las identidades contables que tienen que cumplirse siempre:

    Total activos = Total pasivos + Total patrimonio
    Efectivo inicial + variación del período = Efectivo final

Si alguna falla, o el mapeo cuenta→rubro tiene un hueco o el estado suma mal.
"""

import csv

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import flt

from tz_gobierno.digecog import estados, mapeo
from tz_gobierno.digecog.coa_import import crear_company_sin_coa_estandar, ruta_csv
from tz_gobierno.digecog.reparacion_csv import reparar
from tz_gobierno.setup.sitio import asegurar_fiscal_year

COMPANY = "TZ Gob EEFF"
ABBR = "TGE"

# Códigos reales del plan DIGECOG. El último segmento de cada hoja es imputable.
CUENTAS = [
	("1", "ACTIVO", "Asset", 1),
	("1.1", "Activo Corriente", "Asset", 1),
	("1.1.01", "Efectivo y equivalentes de efectivo", "Asset", 1),
	("1.1.01.01", "Banco de prueba", "Asset", 0),
	("2", "PASIVO", "Liability", 1),
	("2.1", "Pasivo Corriente", "Liability", 1),
	("2.1.01", "Cuentas a pagar a corto plazo", "Liability", 1),
	("2.1.01.01", "Proveedores de prueba", "Liability", 0),
	("3", "PATRIMONIO", "Equity", 1),
	("3.1", "Patrimonio público", "Equity", 1),
	("3.1.01", "Capital", "Equity", 1),
	("3.1.01.01", "Capital aportado de prueba", "Equity", 0),
	("4", "INGRESOS", "Income", 1),
	("4.1", "Impuestos", "Income", 1),
	("4.1.01", "Impuestos sobre los ingresos", "Income", 1),
	("4.1.01.01", "Impuesto sobre la renta de prueba", "Income", 0),
	("5", "GASTOS", "Expense", 1),
	("5.1", "Gastos de operación", "Expense", 1),
	("5.1.01", "Beneficios a los empleados", "Expense", 1),
	("5.1.01.01", "Sueldos de prueba", "Expense", 0),
]

CAPITAL_APORTADO = 10000.0
IMPUESTOS_COBRADOS = 5000.0
SUELDOS_PAGADOS = 3000.0
RESULTADO_ESPERADO = IMPUESTOS_COBRADOS - SUELDOS_PAGADOS
EFECTIVO_FINAL = CAPITAL_APORTADO + IMPUESTOS_COBRADOS - SUELDOS_PAGADOS


class TestMapeoDigecog(UnitTestCase):
	"""El mapeo tiene que cubrir TODAS las cuentas imputables del plan.

	Una cuenta imputable sin rubro es un saldo que desaparece del estado y lo
	descuadra. Se valida contra el plan completo, no contra una muestra.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		with open(ruta_csv(), encoding="utf-8") as f:
			filas, _ = reparar(list(csv.DictReader(f)))
		cls.imputables = [f for f in filas if f["is_group"] == "0"]

	def _sin_mapear(self, tabla, clases, resolver=None):
		resolver = resolver or (lambda c: mapeo.resolver(c, tabla)[0])
		return [
			f["codigo"]
			for f in self.imputables
			if f["codigo"][0] in clases and not resolver(f["codigo"])
		]

	def test_situacion_financiera_cubre_activo_pasivo_patrimonio(self):
		self.assertEqual(self._sin_mapear(mapeo.SITUACION_FINANCIERA, "123"), [])

	def test_rendimiento_financiero_cubre_ingresos_y_gastos(self):
		self.assertEqual(self._sin_mapear(mapeo.RENDIMIENTO_FINANCIERO, "45"), [])

	def test_objeto_presupuestario_cubre_ingresos_y_gastos(self):
		self.assertEqual(self._sin_mapear(mapeo.OBJETO_PRESUPUESTARIO, "45"), [])

	def test_flujo_efectivo_cubre_toda_contrapartida_posible(self):
		"""Cualquier cuenta puede ser contrapartida de un movimiento de caja."""
		sin = self._sin_mapear(None, "12345", resolver=estados._fila_flujo)
		# Las propias cuentas de efectivo no necesitan clasificación.
		sin = [c for c in sin if not c.startswith(mapeo.PREFIJO_EFECTIVO)]
		self.assertEqual(sin, [])

	def test_prefijo_mas_largo_gana(self):
		"""1.1.04.07 es Pagos anticipados, no Cuentas por cobrar."""
		rubro, _ = mapeo.resolver("1.1.04.07.01.001", mapeo.SITUACION_FINANCIERA)
		self.assertEqual(rubro, "Pagos anticipados")

		rubro, _ = mapeo.resolver("1.1.04.01.01.001", mapeo.SITUACION_FINANCIERA)
		self.assertEqual(rubro, "Cuenta por cobrar a corto plazo")


class TestEstadosFinancieros(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		crear_company_sin_coa_estandar(COMPANY, ABBR)
		cls.fiscal_year = asegurar_fiscal_year()
		cls.anio = int(cls.fiscal_year[:4])
		cls.crear_cuentas()
		cls.registrar_asientos()
		frappe.db.commit()

	@classmethod
	def crear_cuentas(cls):
		cls.por_codigo = {}
		for codigo, nombre, root_type, is_group in CUENTAS:
			existente = frappe.db.get_value(
				"Account", {"account_number": codigo, "company": COMPANY}, "name"
			)
			if existente:
				cls.por_codigo[codigo] = existente
				continue

			padre = codigo.rsplit(".", 1)[0] if "." in codigo else None
			doc = frappe.get_doc(
				{
					"doctype": "Account",
					"company": COMPANY,
					"account_number": codigo,
					"account_name": nombre,
					"parent_account": cls.por_codigo.get(padre),
					"is_group": is_group,
					"root_type": root_type,
					"report_type": "Balance Sheet" if codigo[0] in "123" else "Profit and Loss",
				}
			)
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.insert()
			cls.por_codigo[codigo] = doc.name

	@classmethod
	def registrar_asientos(cls):
		if frappe.db.exists("Journal Entry", {"company": COMPANY, "docstatus": 1}):
			return

		fecha = f"{cls.anio}-03-31"
		asientos = [
			("Aporte de capital", "1.1.01.01", "3.1.01.01", CAPITAL_APORTADO),
			("Cobro de impuestos", "1.1.01.01", "4.1.01.01", IMPUESTOS_COBRADOS),
			("Pago de sueldos", "5.1.01.01", "1.1.01.01", SUELDOS_PAGADOS),
		]

		for titulo, debe, haber, monto in asientos:
			je = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"company": COMPANY,
					"posting_date": fecha,
					"user_remark": titulo,
					"accounts": [
						{"account": cls.por_codigo[debe], "debit_in_account_currency": monto},
						{"account": cls.por_codigo[haber], "credit_in_account_currency": monto},
					],
				}
			)
			je.flags.ignore_permissions = True
			je.insert()
			je.submit()

	def _valor(self, filas, concepto):
		for fila in filas:
			if fila["concepto"] == concepto:
				return flt(fila["monto_actual"])
		self.fail(f"El estado no trae la línea {concepto!r}")

	# ------------------------------------------------------------------ #

	def test_situacion_financiera_cuadra(self):
		filas, sin_mapear = estados.situacion_financiera(COMPANY, f"{self.anio}-12-31")
		self.assertEqual(sin_mapear, [], "hay cuentas con saldo fuera del mapeo")
		self.assertTrue(
			estados.cuadra_situacion_financiera(filas),
			"Total activos != Total pasivos + patrimonio",
		)

	def test_situacion_financiera_montos(self):
		filas, _ = estados.situacion_financiera(COMPANY, f"{self.anio}-12-31")

		self.assertEqual(self._valor(filas, "Efectivo y equivalente de efectivo"), EFECTIVO_FINAL)
		self.assertEqual(self._valor(filas, "Total activos"), EFECTIVO_FINAL)
		self.assertEqual(self._valor(filas, "Capital"), CAPITAL_APORTADO)
		self.assertEqual(
			self._valor(filas, mapeo.RUBRO_RESULTADO_DEL_PERIODO), RESULTADO_ESPERADO
		)
		self.assertEqual(self._valor(filas, "Total pasivos"), 0.0)

	def test_rendimiento_financiero_montos(self):
		filas, sin_mapear = estados.rendimiento_financiero(
			COMPANY, f"{self.anio}-01-01", f"{self.anio}-12-31"
		)
		self.assertEqual(sin_mapear, [])

		self.assertEqual(self._valor(filas, "Impuestos"), IMPUESTOS_COBRADOS)
		self.assertEqual(
			self._valor(filas, "Sueldos, salarios y beneficios a empleados"), SUELDOS_PAGADOS
		)
		self.assertEqual(
			self._valor(filas, "Resultado del período (ahorro/desahorro)"), RESULTADO_ESPERADO
		)

	def test_resultado_es_el_mismo_en_ambos_estados(self):
		"""El ahorro del Rendimiento Financiero es el que va al patrimonio."""
		balance, _ = estados.situacion_financiera(COMPANY, f"{self.anio}-12-31")
		rendimiento, _ = estados.rendimiento_financiero(
			COMPANY, f"{self.anio}-01-01", f"{self.anio}-12-31"
		)
		self.assertEqual(
			self._valor(balance, mapeo.RUBRO_RESULTADO_DEL_PERIODO),
			self._valor(rendimiento, "Resultado del período (ahorro/desahorro)"),
		)

	def test_flujo_efectivo_cuadra(self):
		filas, sin_clasificar = estados.flujo_efectivo(
			COMPANY, f"{self.anio}-01-01", f"{self.anio}-12-31"
		)
		self.assertEqual(sin_clasificar, [], "hay movimientos de caja sin clasificar")
		self.assertTrue(
			estados.cuadra_flujo_efectivo(filas),
			"efectivo inicial + variación != efectivo final",
		)

	def test_flujo_efectivo_clasifica_por_contrapartida(self):
		filas, _ = estados.flujo_efectivo(COMPANY, f"{self.anio}-01-01", f"{self.anio}-12-31")

		self.assertEqual(self._valor(filas, "Cobros impuestos"), IMPUESTOS_COBRADOS)
		self.assertEqual(
			self._valor(filas, "Pagos a los trabajadores o en beneficio de ellos"),
			-SUELDOS_PAGADOS,
		)
		self.assertEqual(self._valor(filas, "Cobro por aporte de accionista"), CAPITAL_APORTADO)
		self.assertEqual(
			self._valor(filas, "Efectivo y equivalentes al efectivo al final del periodo"),
			EFECTIVO_FINAL,
		)

	def test_flujo_efectivo_separa_operacion_de_financiacion(self):
		"""El aporte de capital es financiación, no operación."""
		filas, _ = estados.flujo_efectivo(COMPANY, f"{self.anio}-01-01", f"{self.anio}-12-31")

		self.assertEqual(
			self._valor(filas, "Flujos de efectivo netos de las actividades de operación"),
			IMPUESTOS_COBRADOS - SUELDOS_PAGADOS,
		)
		self.assertEqual(
			self._valor(filas, "Flujos de efectivo netos por las actividades de financiación"),
			CAPITAL_APORTADO,
		)

	def test_estados_respetan_el_layout_oficial(self):
		"""El modelo de DIGECOG es de formato fijo: los rubros van siempre, con o sin saldo."""
		filas, _ = estados.situacion_financiera(COMPANY, f"{self.anio}-12-31")
		conceptos = [f["concepto"] for f in filas]

		for _seccion, rubros in mapeo.ORDEN_SITUACION_FINANCIERA:
			for rubro in rubros:
				self.assertIn(rubro, conceptos)

	def test_comparacion_presupuesto_sin_lineas_da_ceros(self):
		filas = estados.comparacion_presupuesto(COMPANY, self.fiscal_year)
		conceptos = [f["concepto"] for f in filas]

		self.assertIn("1     Ingresos totales", conceptos)
		self.assertIn("2     Gastos totales", conceptos)
		for fila in filas:
			self.assertEqual(flt(fila["presupuesto_ejecutado"]), 0.0)


class TestScriptReports(IntegrationTestCase):
	"""Ejecuta los 5 reportes por la misma vía que usa la UI.

	Los tests de arriba prueban el motor; estos prueban que los Script Report estén
	bien registrados y que sus `execute()` devuelvan columnas y filas sin reventar.
	Sin esto, un reporte podría estar perfecto en Python y roto en el escritorio, que
	es donde lo va a abrir el perito en la demo.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.fiscal_year = asegurar_fiscal_year()
		cls.anio = int(cls.fiscal_year[:4])
		# Reusa la institución de TestEstadosFinancieros si ya fue montada.
		if not frappe.db.exists("Company", COMPANY):
			crear_company_sin_coa_estandar(COMPANY, ABBR)

	def _correr(self, nombre, filtros):
		from frappe.desk.query_report import run

		resultado = run(nombre, filters=filtros, ignore_prepared_report=True)
		self.assertTrue(resultado.get("columns"), f"{nombre} no devolvió columnas")
		return resultado

	def test_los_cinco_reportes_estan_registrados(self):
		esperados = [
			"Estado de Situacion Financiera DIGECOG",
			"Estado de Rendimiento Financiero DIGECOG",
			"Estado de Cambios en Patrimonio DIGECOG",
			"Estado de Flujo de Efectivo DIGECOG",
			"Estado de Comparacion Presupuesto Ejecucion DIGECOG",
		]
		for nombre in esperados:
			self.assertTrue(frappe.db.exists("Report", nombre), f"falta el reporte {nombre}")
			self.assertEqual(
				frappe.db.get_value("Report", nombre, "report_type"), "Script Report"
			)

	def test_situacion_financiera_corre(self):
		r = self._correr(
			"Estado de Situacion Financiera DIGECOG",
			{"company": COMPANY, "as_on_date": f"{self.anio}-12-31",
			 "mostrar_periodo_anterior": 1},
		)
		self.assertEqual(len(r["columns"]), 3)

	def test_rendimiento_financiero_corre(self):
		self._correr(
			"Estado de Rendimiento Financiero DIGECOG",
			{"company": COMPANY, "from_date": f"{self.anio}-01-01",
			 "to_date": f"{self.anio}-12-31", "mostrar_periodo_anterior": 0},
		)

	def test_flujo_efectivo_corre(self):
		self._correr(
			"Estado de Flujo de Efectivo DIGECOG",
			{"company": COMPANY, "from_date": f"{self.anio}-01-01",
			 "to_date": f"{self.anio}-12-31"},
		)

	def test_cambios_patrimonio_corre(self):
		r = self._correr(
			"Estado de Cambios en Patrimonio DIGECOG",
			{"company": COMPANY, "fiscal_year": self.fiscal_year},
		)
		# Concepto + 4 componentes del patrimonio + total.
		self.assertEqual(len(r["columns"]), 6)

	def test_comparacion_presupuesto_corre(self):
		r = self._correr(
			"Estado de Comparacion Presupuesto Ejecucion DIGECOG",
			{"company": COMPANY, "fiscal_year": self.fiscal_year},
		)
		self.assertEqual(len(r["columns"]), 5)

	def test_reportes_sin_filtros_no_revientan(self):
		"""Al abrirlos el usuario ve el reporte vacío, no un traceback."""
		from frappe.desk.query_report import run

		for nombre in ("Estado de Situacion Financiera DIGECOG",
		               "Estado de Flujo de Efectivo DIGECOG"):
			resultado = run(nombre, filters={}, ignore_prepared_report=True)
			self.assertEqual(resultado.get("result"), [])
