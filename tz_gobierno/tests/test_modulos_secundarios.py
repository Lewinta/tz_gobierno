# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Tests de los módulos secundarios (§7 del spec CES-0009).

Lotes de tarjeta de crédito, préstamos bancarios al personal, encuestas y etiquetas
de activos. Todos comparten la misma institución de prueba para no repetir el montaje.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, nowdate

from tz_gobierno import activos, encuestas
from tz_gobierno.digecog.coa_import import crear_company_sin_coa_estandar
from tz_gobierno.setup.sitio import asegurar_fiscal_year, sembrar_masters

COMPANY = "TZ Gob Secundarios"
ABBR = "TGS"


def _cuenta(nombre, root_type, padre=None, is_group=0, account_type=None):
	existente = frappe.db.get_value(
		"Account", {"account_name": nombre, "company": COMPANY}, "name"
	)
	if existente:
		return existente

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
	doc.flags.ignore_mandatory = True
	doc.insert()
	return doc.name


class BaseSecundarios(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sembrar_masters()
		crear_company_sin_coa_estandar(COMPANY, ABBR)
		cls.fiscal_year = asegurar_fiscal_year()

		gastos = _cuenta("Gastos TGS", "Expense", is_group=1)
		cls.cuenta_gasto = _cuenta("Viáticos TGS", "Expense", padre=gastos)
		cls.cuenta_gasto2 = _cuenta("Combustible TGS", "Expense", padre=gastos)

		pasivos = _cuenta("Pasivos TGS", "Liability", is_group=1)
		cls.cuenta_tarjeta = _cuenta("Tarjeta Corporativa TGS", "Liability", padre=pasivos)

		cls.cost_center = f"Main - {ABBR}"
		frappe.db.commit()


class TestLoteTarjetaCredito(BaseSecundarios):
	def _lote(self, consumos=None, periodo=None):
		consumos = consumos or [
			{"fecha": nowdate(), "comercio": "Estación de servicio",
			 "monto": 1500, "account": self.cuenta_gasto2, "cost_center": self.cost_center},
			{"fecha": nowdate(), "comercio": "Hotel Santo Domingo",
			 "monto": 4200, "account": self.cuenta_gasto, "cost_center": self.cost_center},
			{"fecha": nowdate(), "comercio": "Restaurante",
			 "monto": 800, "account": self.cuenta_gasto, "cost_center": self.cost_center},
		]
		doc = frappe.get_doc(
			{
				"doctype": "Lote Tarjeta Credito",
				"banco": "Banreservas",
				"ultimos_4_digitos": "4321",
				"company": COMPANY,
				"periodo": periodo or frappe.generate_hash(length=6),
				"fecha_corte": nowdate(),
				"cuenta_tarjeta": self.cuenta_tarjeta,
				"consumos": consumos,
			}
		)
		doc.flags.ignore_permissions = True
		return doc.insert()

	def test_el_total_se_calcula_de_los_consumos(self):
		lote = self._lote()
		self.assertEqual(flt(lote.monto_total), 6500.0)

	def test_genera_asiento_cuadrado(self):
		lote = self._lote()
		nombre = lote.generar_asiento()

		asiento = frappe.get_doc("Journal Entry", nombre)
		debe = sum(flt(f.debit_in_account_currency) for f in asiento.accounts)
		haber = sum(flt(f.credit_in_account_currency) for f in asiento.accounts)

		self.assertEqual(debe, haber, "el asiento no cuadra")
		self.assertEqual(debe, flt(lote.monto_total),
		                 "el asiento no suma el total del lote")
		# Una línea por consumo más la contrapartida de la tarjeta.
		self.assertEqual(len(asiento.accounts), len(lote.consumos) + 1)

	def test_el_asiento_queda_en_borrador(self):
		"""Quien concilia la tarjeta no es quien aprueba el asiento."""
		lote = self._lote()
		asiento = frappe.get_doc("Journal Entry", lote.generar_asiento())
		self.assertEqual(asiento.docstatus, 0)

	def test_no_genera_el_asiento_dos_veces(self):
		lote = self._lote()
		lote.generar_asiento()
		lote.reload()
		with self.assertRaises(frappe.ValidationError):
			lote.generar_asiento()

	def test_rechaza_consumo_contra_cuenta_de_grupo(self):
		grupo = frappe.db.get_value("Account", self.cuenta_gasto, "parent_account")
		with self.assertRaises(frappe.ValidationError):
			self._lote(consumos=[
				{"fecha": nowdate(), "comercio": "X", "monto": 100,
				 "account": grupo, "cost_center": self.cost_center}
			])

	def test_la_cuenta_de_la_tarjeta_debe_ser_pasivo(self):
		doc = frappe.get_doc(
			{
				"doctype": "Lote Tarjeta Credito",
				"banco": "Popular",
				"ultimos_4_digitos": "9999",
				"company": COMPANY,
				"periodo": frappe.generate_hash(length=6),
				"fecha_corte": nowdate(),
				"cuenta_tarjeta": self.cuenta_gasto,  # es de gasto, no de pasivo
				"consumos": [
					{"fecha": nowdate(), "comercio": "X", "monto": 100,
					 "account": self.cuenta_gasto2, "cost_center": self.cost_center}
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_no_concilia_sin_asiento(self):
		lote = self._lote()
		with self.assertRaises(frappe.ValidationError):
			lote.marcar_conciliado()


class TestPrestamoBancarioEmpleado(BaseSecundarios):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.employee = cls.asegurar_empleado()
		frappe.db.commit()

	@classmethod
	def asegurar_empleado(cls):
		existente = frappe.db.get_value("Employee", {"company": COMPANY}, "name")
		if existente:
			return existente

		# El sitio puede no traer los masters de género; Employee los exige.
		if not frappe.db.exists("Gender", "Other"):
			frappe.get_doc({"doctype": "Gender", "gender": "Other"}).insert(
				ignore_permissions=True
			)

		doc = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "Empleado",
				"last_name": "De Prueba",
				"company": COMPANY,
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"gender": "Other",
				"status": "Active",
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		return doc.insert().name

	def _prestamo(self, cuotas=12, pagadas=0, cuota=5000):
		frappe.db.delete("Prestamo Bancario Empleado", {"employee": self.employee})
		doc = frappe.get_doc(
			{
				"doctype": "Prestamo Bancario Empleado",
				"employee": self.employee,
				"company": COMPANY,
				"banco": "Banreservas",
				"fecha_inicio": nowdate(),
				"monto_prestamo": cuota * cuotas,
				"cuota_mensual": cuota,
				"numero_cuotas": cuotas,
				"cuotas_pagadas": pagadas,
			}
		)
		doc.flags.ignore_permissions = True
		return doc.insert()

	def test_saldo_pendiente_sale_de_las_cuotas_restantes(self):
		prestamo = self._prestamo(cuotas=12, pagadas=3, cuota=5000)
		self.assertEqual(flt(prestamo.saldo_pendiente), 9 * 5000)

	def test_queda_saldado_al_pagar_la_ultima_cuota(self):
		prestamo = self._prestamo(cuotas=3, pagadas=2, cuota=1000)
		self.assertEqual(prestamo.estado, "Activo")

		prestamo.registrar_cuota()
		prestamo.reload()
		self.assertEqual(int(prestamo.cuotas_pagadas), 3)
		self.assertEqual(flt(prestamo.saldo_pendiente), 0.0)
		self.assertEqual(prestamo.estado, "Saldado")

	def test_un_prestamo_saldado_deja_de_estar_vigente(self):
		prestamo = self._prestamo(cuotas=1, pagadas=1, cuota=1000)
		self.assertFalse(prestamo.esta_vigente())

	def test_no_admite_mas_cuotas_pagadas_que_el_total(self):
		with self.assertRaises(frappe.ValidationError):
			self._prestamo(cuotas=3, pagadas=5)

	def test_no_admite_cuota_en_cero(self):
		with self.assertRaises(frappe.ValidationError):
			self._prestamo(cuota=0)

	def test_solo_devuelve_vigentes(self):
		from tz_gobierno.tz_gobierno.doctype.prestamo_bancario_empleado.prestamo_bancario_empleado import (
			prestamos_vigentes,
		)

		self._prestamo(cuotas=6, pagadas=1)
		vigentes = prestamos_vigentes(self.employee, COMPANY)
		self.assertEqual(len(vigentes), 1)

		vigentes[0].db_set("estado", "Suspendido")
		self.assertEqual(prestamos_vigentes(self.employee, COMPANY), [])


class TestEncuestas(BaseSecundarios):
	def _encuesta(self):
		titulo = f"Clima laboral {frappe.generate_hash(length=6)}"
		doc = frappe.get_doc(
			{
				"doctype": "Encuesta",
				"titulo": titulo,
				"activa": 1,
				"fecha_inicio": nowdate(),
				"preguntas": [
					{"texto": "¿Cómo calificas el ambiente?", "tipo_respuesta": "Escala 1-5"},
					{"texto": "¿Qué turno prefieres?", "tipo_respuesta": "Selección múltiple",
					 "opciones": "Matutino\nVespertino\nMixto"},
					{"texto": "Comentarios", "tipo_respuesta": "Texto abierto"},
				],
			}
		)
		doc.flags.ignore_permissions = True
		return doc.insert()

	def _responder(self, encuesta, escala, turno, comentario):
		doc = frappe.get_doc(
			{
				"doctype": "Respuesta Encuesta",
				"encuesta": encuesta.name,
				"anonima": 1,
				"fecha": nowdate(),
				"respuestas": [
					{"pregunta": encuesta.preguntas[0].texto, "respuesta": str(escala)},
					{"pregunta": encuesta.preguntas[1].texto, "respuesta": turno},
					{"pregunta": encuesta.preguntas[2].texto, "respuesta": comentario},
				],
			}
		)
		doc.flags.ignore_permissions = True
		return doc.insert()

	def test_agrega_escala_por_promedio_y_seleccion_por_conteo(self):
		encuesta = self._encuesta()
		self._responder(encuesta, 5, "Matutino", "Todo bien")
		self._responder(encuesta, 3, "Matutino", "Falta café")
		self._responder(encuesta, 4, "Mixto", "Sin comentarios")

		resultado = {r["pregunta"]: r for r in encuestas.resultados(encuesta.name)}

		escala = resultado["¿Cómo calificas el ambiente?"]
		self.assertEqual(escala["total_respuestas"], 3)
		self.assertAlmostEqual(escala["promedio"], 4.0, places=2)

		seleccion = resultado["¿Qué turno prefieres?"]
		self.assertEqual(seleccion["conteos"]["Matutino"], 2)
		self.assertEqual(seleccion["conteos"]["Mixto"], 1)
		self.assertEqual(seleccion["conteos"]["Vespertino"], 0)

		texto = resultado["Comentarios"]
		self.assertEqual(len(texto["textos"]), 3)
		self.assertNotIn("promedio", texto, "el texto abierto no se promedia")

	def test_rechaza_valor_fuera_de_la_escala(self):
		encuesta = self._encuesta()
		with self.assertRaises(frappe.ValidationError):
			self._responder(encuesta, 9, "Matutino", "x")

	def test_rechaza_opcion_inexistente(self):
		encuesta = self._encuesta()
		with self.assertRaises(frappe.ValidationError):
			self._responder(encuesta, 3, "Nocturno", "x")

	def test_rechaza_pregunta_ajena_a_la_encuesta(self):
		encuesta = self._encuesta()
		doc = frappe.get_doc(
			{
				"doctype": "Respuesta Encuesta",
				"encuesta": encuesta.name,
				"fecha": nowdate(),
				"respuestas": [{"pregunta": "Pregunta que no existe", "respuesta": "1"}],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_una_respuesta_anonima_no_guarda_el_empleado(self):
		"""Si guarda el empleado, no es anónima."""
		encuesta = self._encuesta()
		empleado = frappe.db.get_value("Employee", {"company": COMPANY}, "name")
		doc = frappe.get_doc(
			{
				"doctype": "Respuesta Encuesta",
				"encuesta": encuesta.name,
				"anonima": 1,
				"employee": empleado,
				"fecha": nowdate(),
				"respuestas": [
					{"pregunta": encuesta.preguntas[0].texto, "respuesta": "4"}
				],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		self.assertFalse(doc.employee)


class TestEtiquetaActivo(BaseSecundarios):
	def test_el_campo_de_bienes_nacionales_existe_en_asset(self):
		activos.asegurar_campo_bienes_nacionales()
		self.assertTrue(
			frappe.db.exists(
				"Custom Field",
				{"dt": "Asset", "fieldname": activos.CAMPO_BIENES_NACIONALES},
			)
		)

	def test_genera_un_qr_svg_valido(self):
		svg = activos.qr_svg("CES-BN-000123")
		self.assertIn("<svg", svg)
		self.assertIn("</svg>", svg)
		self.assertIn('width="90"', svg)

	def test_sin_codigo_no_hay_qr(self):
		"""Un activo pendiente de registrar en Bienes Nacionales igual imprime etiqueta."""
		self.assertEqual(activos.qr_svg(""), "")
		self.assertEqual(activos.qr_svg(None), "")

	def test_el_print_format_esta_registrado(self):
		self.assertTrue(frappe.db.exists("Print Format", "Etiqueta Activo QR"))
		self.assertEqual(
			frappe.db.get_value("Print Format", "Etiqueta Activo QR", "doc_type"), "Asset"
		)
