# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Tests de los módulos que dependen de un insumo externo (§8 del spec).

Estos tres módulos están bloqueados por documentos que solo el CES o Banreservas
pueden entregar. Lo que se prueba aquí es justamente que la parte parametrizable
funcione: que un cambio de configuración cambie el resultado sin tocar código, que es
lo que permitirá absorber el layout real cuando llegue.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, nowdate

from tz_gobierno import nomina_bancaria
from tz_gobierno.digecog.coa_import import crear_company_sin_coa_estandar
from tz_gobierno.setup import banreservas
from tz_gobierno.setup.sitio import asegurar_fiscal_year, sembrar_masters

COMPANY = "TZ Gob Param"
ABBR = "TGP"


class BaseParametrizables(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sembrar_masters()
		crear_company_sin_coa_estandar(COMPANY, ABBR)
		cls.fiscal_year = asegurar_fiscal_year()
		frappe.db.commit()


class TestNominaBancaria(BaseParametrizables):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.config = cls.config_csv()
		frappe.db.commit()

	@classmethod
	def config_csv(cls):
		nombre = "Banco de Prueba CSV"
		if frappe.db.exists("Banco Nomina Config", nombre):
			return nombre
		doc = frappe.get_doc(
			{
				"doctype": "Banco Nomina Config",
				"banco": nombre,
				"company": COMPANY,
				"formato_archivo": "CSV",
				"delimitador": ",",
				"extension": "csv",
				"verificado": 1,
				"columnas": [
					{"posicion": 2, "campo": "Nombre completo"},
					{"posicion": 1, "campo": "Cuenta bancaria del empleado"},
					{"posicion": 3, "campo": "Monto neto"},
				],
			}
		)
		doc.flags.ignore_permissions = True
		return doc.insert().name

	def _filas_falsas(self):
		return [
			{"employee": "E1", "employee_name": "Ana Pérez", "net_pay": 45000.5,
			 "bank_ac_no": "9601234567", "bank_name": "Banreservas", "ifsc_code": "BRRD",
			 "cedula": "00112345678"},
			{"employee": "E2", "employee_name": "Luis Gómez", "net_pay": 38250.0,
			 "bank_ac_no": "9607654321", "bank_name": "Banreservas", "ifsc_code": "BRRD",
			 "cedula": "00287654321"},
		]

	def test_las_columnas_salen_en_el_orden_configurado(self):
		"""La posición manda, no el orden en que se cargaron las filas."""
		config = frappe.get_doc("Banco Nomina Config", self.config)
		columnas = sorted(config.columnas, key=lambda c: int(c.posicion))
		contenido = nomina_bancaria._generar_csv(self._filas_falsas(), columnas, ",")

		primera = contenido.splitlines()[0]
		self.assertTrue(primera.startswith("9601234567,Ana Pérez,45000.50"), primera)

	def test_el_ancho_fijo_respeta_ancho_y_relleno(self):
		columnas = [
			frappe._dict(campo="Cédula", ancho=11, relleno="Izquierda", valor_fijo=None),
			frappe._dict(campo="Nombre completo", ancho=10, relleno="Derecha", valor_fijo=None),
		]
		contenido = nomina_bancaria._generar_ancho_fijo(self._filas_falsas()[:1], columnas)
		linea = contenido.splitlines()[0]

		self.assertEqual(len(linea), 21)
		self.assertEqual(linea[:11], "00112345678")
		# Relleno a la derecha: el nombre queda pegado a la izquierda del campo.
		self.assertEqual(linea[11:], "Ana Pérez ")

	def test_el_ancho_fijo_trunca_lo_que_no_cabe(self):
		columnas = [frappe._dict(campo="Nombre completo", ancho=4, relleno="Derecha",
		                         valor_fijo=None)]
		contenido = nomina_bancaria._generar_ancho_fijo(self._filas_falsas()[:1], columnas)
		self.assertEqual(contenido.splitlines()[0], "Ana ")

	def test_el_texto_fijo_sale_igual_en_todas_las_filas(self):
		columnas = [frappe._dict(campo="Texto fijo", valor_fijo="01", ancho=0, relleno=None)]
		contenido = nomina_bancaria._generar_csv(self._filas_falsas(), columnas, ",")
		self.assertEqual(contenido.splitlines(), ["01", "01"])

	def test_el_xml_trae_una_etiqueta_por_pago(self):
		config = frappe.get_doc("Banco Nomina Config", self.config)
		columnas = sorted(config.columnas, key=lambda c: int(c.posicion))
		contenido = nomina_bancaria._generar_xml(
			self._filas_falsas(), columnas, frappe._dict(banco="Banco X")
		)
		self.assertEqual(contenido.count("<pago>"), 2)
		self.assertIn("<monto_neto>45000.50</monto_neto>", contenido)

	def test_el_xml_escapa_caracteres_especiales(self):
		filas = [{"employee_name": "Pérez & Asociados <SRL>", "net_pay": 1.0,
		          "bank_ac_no": "1", "cedula": "1"}]
		columnas = [frappe._dict(campo="Nombre completo", ancho=0, relleno=None, valor_fijo=None)]
		contenido = nomina_bancaria._generar_xml(filas, columnas, frappe._dict(banco="X"))
		self.assertIn("P&#233;rez &amp; Asociados &lt;SRL&gt;".replace("&#233;", "é"), contenido)
		self.assertNotIn("<SRL>", contenido)

	def test_una_config_sin_columnas_falla_en_vez_de_generar_vacio(self):
		nombre = "Banco Sin Columnas"
		if not frappe.db.exists("Banco Nomina Config", nombre):
			doc = frappe.get_doc(
				{
					"doctype": "Banco Nomina Config",
					"banco": nombre,
					"company": COMPANY,
					"formato_archivo": "CSV",
					"verificado": 1,
				}
			)
			doc.flags.ignore_permissions = True
			doc.insert()

		with self.assertRaises(frappe.ValidationError):
			nomina_bancaria.generar("PAYROLL-INEXISTENTE", nombre)

	def test_la_config_de_banreservas_queda_marcada_como_no_verificada(self):
		"""El layout real lo entrega el banco; hasta entonces hay que advertirlo."""
		nombre = banreservas.crear(COMPANY)
		config = frappe.get_doc("Banco Nomina Config", nombre)

		self.assertEqual(int(config.verificado), 0)
		self.assertTrue(config.columnas, "la config de ejemplo debe traer columnas")


class TestImportacionSIAB(BaseParametrizables):
	def _importacion(self, mapeo=None):
		doc = frappe.get_doc(
			{
				"doctype": "Importacion SIAB",
				"company": COMPANY,
				"archivo": "/files/no-usado-en-este-test.csv",
				"fecha_importacion": nowdate(),
				"mapeo_columnas": mapeo,
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		return doc

	def test_sin_mapeo_se_usa_el_layout_de_referencia(self):
		doc = self._importacion()
		doc.validar_mapeo()
		mapeo = json.loads(doc.mapeo_columnas)

		self.assertEqual(mapeo["Código B.N."], "codigo_bienes_nacionales")
		self.assertEqual(mapeo["Descripción"], "asset_name")

	def test_un_mapeo_invalido_falla_con_mensaje_claro(self):
		doc = self._importacion(mapeo="{esto no es json}")
		with self.assertRaises(frappe.ValidationError):
			doc.validar_mapeo()

	def test_el_mapeo_debe_ser_un_objeto(self):
		doc = self._importacion(mapeo='["una", "lista"]')
		with self.assertRaises(frappe.ValidationError):
			doc.validar_mapeo()

	def test_el_mapeo_es_configurable(self):
		"""Cuando llegue la exportación real del CES, esto es lo que cambia."""
		propio = json.dumps({"COD_BN": "codigo_bienes_nacionales", "DESC": "asset_name"})
		doc = self._importacion(mapeo=propio)
		doc.validar_mapeo()

		self.assertEqual(doc.mapeo()["COD_BN"], "codigo_bienes_nacionales")
		self.assertNotIn("Código B.N.", doc.mapeo())

	def test_traduce_una_fila_segun_el_mapeo(self):
		doc = self._importacion()
		doc.validar_mapeo()
		fila = {"Código B.N.": "BN-001", "Descripción": "Escritorio", "Fecha": "2026-01-15"}

		activo = doc._a_activo(fila, doc.mapeo())
		self.assertEqual(activo["codigo_bienes_nacionales"], "BN-001")
		self.assertEqual(activo["asset_name"], "Escritorio")
		self.assertEqual(activo["purchase_date"], "2026-01-15")


class TestSolicitudTramitePago(BaseParametrizables):
	def _solicitud(self, monto=1000, linea=None):
		doc = frappe.get_doc(
			{
				"doctype": "Solicitud Tramite Pago",
				"company": COMPANY,
				"tipo_tramite": "Bienes y servicios",
				"fecha": nowdate(),
				"tipo_orden_pago": "Transferencia",
				"beneficiario": "Suplidor de prueba",
				"concepto": "Compra de materiales de oficina",
				"monto": monto,
				"linea_presupuestaria": linea,
			}
		)
		doc.flags.ignore_permissions = True
		return doc

	def test_se_crea_con_los_campos_del_formulario_publico(self):
		doc = self._solicitud().insert()
		self.assertTrue(doc.name.startswith("STP-"))
		self.assertEqual(doc.estado, "Borrador")

	def test_rechaza_monto_en_cero(self):
		with self.assertRaises(frappe.ValidationError):
			self._solicitud(monto=0).insert()

	def test_sin_linea_presupuestaria_no_valida_disponibilidad(self):
		"""La línea es opcional: hay trámites que no consumen presupuesto propio."""
		doc = self._solicitud(linea=None).insert()
		self.assertFalse(doc.linea_presupuestaria)


class TestNotasEstadosFinancieros(BaseParametrizables):
	"""§5.6 — el manual exige seis notas obligatorias."""

	def _nota(self, tipo, orden):
		doc = frappe.get_doc(
			{
				"doctype": "Nota Estado Financiero",
				"company": COMPANY,
				"fiscal_year": self.fiscal_year,
				"tipo": tipo,
				"orden": orden,
				"contenido": f"<p>Contenido de la nota {tipo}.</p>",
			}
		)
		doc.flags.ignore_permissions = True
		return doc.insert()

	def _correr(self):
		from frappe.desk.query_report import run

		return run(
			"Notas a los Estados Financieros DIGECOG",
			filters={"company": COMPANY, "fiscal_year": self.fiscal_year},
			ignore_prepared_report=True,
		)

	def test_el_reporte_lista_las_notas_en_orden(self):
		frappe.db.delete("Nota Estado Financiero", {"company": COMPANY})
		self._nota("Base de medición", 5)
		self._nota("Entidad económica", 1)
		self._nota("Base de presentación", 2)

		resultado = self._correr()
		ordenes = [f["orden"] for f in resultado["result"]]
		self.assertEqual(ordenes, sorted(ordenes))
		self.assertEqual(resultado["result"][0]["tipo"], "Entidad económica")

	def test_avisa_cuando_falta_una_nota_obligatoria(self):
		from tz_gobierno.tz_gobierno.report.notas_a_los_estados_financieros_digecog import (
			notas_a_los_estados_financieros_digecog as reporte,
		)

		frappe.db.delete("Nota Estado Financiero", {"company": COMPANY})
		self._nota("Entidad económica", 1)

		frappe.message_log = []
		reporte.execute({"company": COMPANY, "fiscal_year": self.fiscal_year})
		mensajes = " ".join(str(m) for m in frappe.message_log)

		self.assertIn("Base de presentación", mensajes)
		self.assertIn("Resumen de políticas contables", mensajes)

	def test_no_avisa_cuando_estan_las_seis(self):
		from tz_gobierno.tz_gobierno.report.notas_a_los_estados_financieros_digecog import (
			notas_a_los_estados_financieros_digecog as reporte,
		)

		frappe.db.delete("Nota Estado Financiero", {"company": COMPANY})
		for orden, tipo in enumerate(reporte.NOTAS_OBLIGATORIAS, start=1):
			self._nota(tipo, orden)

		frappe.message_log = []
		columnas, filas = reporte.execute(
			{"company": COMPANY, "fiscal_year": self.fiscal_year}
		)

		self.assertEqual(len(filas), 6)
		self.assertEqual(frappe.message_log, [])
