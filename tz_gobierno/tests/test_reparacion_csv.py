# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Tests de la reparación del CSV del plan DIGECOG.

Son unitarios puros (no tocan la base) para que corran rápido y para poder fijar
con precisión los números del defecto de extracción: si alguien regenera el CSV y
los conteos cambian, estos tests lo detectan antes de importar nada.
"""

import csv

from frappe.tests import UnitTestCase

from tz_gobierno.digecog.coa_import import (
	CONTEO_POR_ROOT_TYPE,
	CONTEO_POR_ROOT_TYPE_CSV_CRUDO,
	FILAS_CSV_DIGECOG,
	TOTAL_CUENTAS_DIGECOG,
	ruta_csv,
)
from tz_gobierno.digecog.reparacion_csv import (
	ReparacionError,
	reparar,
	reparar_fila,
)


def _crudo():
	with open(ruta_csv(), encoding="utf-8") as f:
		return list(csv.DictReader(f))


class TestReparacionCSV(UnitTestCase):
	def test_csv_crudo_tiene_los_conteos_del_spec(self):
		"""Fija el punto de partida: el CSV tal como lo entregó la extracción."""
		filas = _crudo()
		self.assertEqual(len(filas), FILAS_CSV_DIGECOG)

		por_root = {}
		for fila in filas:
			por_root[fila["root_type"]] = por_root.get(fila["root_type"], 0) + 1

		self.assertEqual(por_root, CONTEO_POR_ROOT_TYPE_CSV_CRUDO)

	def test_reparacion_recupera_las_80_cuentas_perdidas(self):
		filas, informe = reparar(_crudo())

		self.assertEqual(informe["filas_con_nombre_corrupto"], 40)
		self.assertEqual(informe["cuentas_recuperadas"], 80)
		self.assertEqual(informe["filas_resultantes"], TOTAL_CUENTAS_DIGECOG)
		self.assertEqual(len(filas), TOTAL_CUENTAS_DIGECOG)

	def test_conteos_por_root_type_tras_reparar(self):
		filas, _ = reparar(_crudo())

		por_root = {}
		for fila in filas:
			por_root[fila["root_type"]] = por_root.get(fila["root_type"], 0) + 1

		self.assertEqual(por_root, CONTEO_POR_ROOT_TYPE)

	def test_no_quedan_nombres_con_codigos_embebidos(self):
		from tz_gobierno.digecog.reparacion_csv import fila_esta_corrupta

		filas, _ = reparar(_crudo())
		corruptas = [f["codigo"] for f in filas if fila_esta_corrupta(f)]
		self.assertEqual(corruptas, [])

	def test_unico_huerfano_es_el_conocido_4_9_99(self):
		"""4.9.99 declara padre 4.9, que no existe en el documento de DIGECOG."""
		filas, _ = reparar(_crudo())
		codigos = {f["codigo"].strip() for f in filas}

		huerfanos = sorted(
			f["codigo"].strip()
			for f in filas
			if f["codigo_padre"].strip() and f["codigo_padre"].strip() not in codigos
		)
		self.assertEqual(huerfanos, ["4.9.99"])

	def test_ninguna_cuenta_con_hijos_queda_como_ledger(self):
		"""ERPNext lanza si un Account con hijos no es is_group."""
		filas, informe = reparar(_crudo())

		por_codigo = {f["codigo"].strip(): f for f in filas}
		con_hijos = {f["codigo_padre"].strip() for f in filas if f["codigo_padre"].strip()}

		conflictos = [c for c in con_hijos if c in por_codigo and por_codigo[c]["is_group"] == "0"]
		self.assertEqual(conflictos, [])
		self.assertEqual(len(informe["regrupadas"]), 18)

	def test_no_muta_la_lista_de_entrada(self):
		filas = _crudo()
		copia = [dict(f) for f in filas]
		reparar(filas)
		self.assertEqual(filas, copia)

	def test_padre_de_recuperada_sale_de_su_propio_codigo(self):
		"""29 de los 80 embebidos son hermanos, no hijos, de la fila que los contenía."""
		filas, _ = reparar(_crudo())
		recuperadas = [f for f in filas if f.get("_recuperada")]

		self.assertTrue(recuperadas)
		for fila in recuperadas:
			self.assertEqual(fila["codigo_padre"], fila["codigo"].rsplit(".", 1)[0])

		hermanas = [f for f in recuperadas if f["codigo_padre"] != f["_hallada_en"]]
		self.assertEqual(len(hermanas), 29)

	def test_parser_lanza_ante_forma_desconocida(self):
		"""El parser nunca adivina: si la forma no es la esperada, falla ruidosamente."""
		fila = {
			"codigo": "1.1",
			"nombre_cuenta": "Algo raro 1.1.01 nivel insuficiente S",
			"root_type": "Asset",
		}
		with self.assertRaises(ReparacionError):
			reparar_fila(fila)
