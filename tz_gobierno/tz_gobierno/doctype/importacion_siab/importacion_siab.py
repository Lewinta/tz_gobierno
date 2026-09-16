# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Importación de activos desde SIAB (§8 del spec).

El layout exacto que exporta el SIAB del CES no está confirmado. Se toma como
plantilla el reporte real de SIAB que sí es público (el de Prodominicana) y el mapeo
de columnas se deja **configurable**, no fijo: cuando el CES entregue su exportación
real, se ajusta el JSON del mapeo en vez de tocar el código.
"""

import csv
import io
import json

import frappe
from frappe import _
from frappe.model.document import Document

# Columnas del reporte SIAB confirmado como público (Prodominicana).
MAPEO_POR_DEFECTO = {
	"Código B.N.": "codigo_bienes_nacionales",
	"Descripción": "asset_name",
	"Fecha": "purchase_date",
	"Responsable": "custodian",
	"Depto.": "department",
}


class ImportacionSIAB(Document):
	def validate(self):
		self.validar_mapeo()

	def validar_mapeo(self):
		if not self.mapeo_columnas:
			self.mapeo_columnas = json.dumps(MAPEO_POR_DEFECTO, ensure_ascii=False, indent=2)
			return

		try:
			mapeo = json.loads(self.mapeo_columnas)
		except ValueError as error:
			frappe.throw(_("El mapeo de columnas no es JSON válido: {0}").format(error))

		if not isinstance(mapeo, dict):
			frappe.throw(_("El mapeo de columnas debe ser un objeto {columna: campo}."))

	def mapeo(self):
		return json.loads(self.mapeo_columnas) if self.mapeo_columnas else MAPEO_POR_DEFECTO

	def leer_filas(self):
		if not self.archivo:
			frappe.throw(_("Adjunte el archivo CSV exportado del SIAB."))

		archivo = frappe.get_doc("File", {"file_url": self.archivo})
		contenido = archivo.get_content()
		if isinstance(contenido, bytes):
			contenido = contenido.decode("utf-8-sig")

		return list(csv.DictReader(io.StringIO(contenido)))

	@frappe.whitelist()
	def previsualizar(self):
		"""Muestra qué se crearía, sin crear nada.

		Importar activos es difícil de deshacer, así que conviene poder mirar antes.
		"""
		filas = self.leer_filas()
		mapeo = self.mapeo()
		faltantes = [c for c in mapeo if filas and c not in filas[0]]

		return {
			"total_filas": len(filas),
			"columnas_del_archivo": list(filas[0].keys()) if filas else [],
			"columnas_mapeadas_ausentes": faltantes,
			"muestra": [self._a_activo(f, mapeo) for f in filas[:5]],
		}

	def _a_activo(self, fila, mapeo):
		datos = {}
		for columna, campo in mapeo.items():
			valor = (fila.get(columna) or "").strip()
			if valor:
				datos[campo] = valor
		return datos

	@frappe.whitelist()
	def importar(self):
		"""Crea los Asset. Idempotente por código de Bienes Nacionales."""
		filas = self.leer_filas()
		mapeo = self.mapeo()

		creados, omitidos, errores = 0, 0, []

		for indice, fila in enumerate(filas, start=2):  # 1 es el encabezado
			datos = self._a_activo(fila, mapeo)
			codigo = datos.get("codigo_bienes_nacionales")

			if not datos.get("asset_name"):
				errores.append(f"Fila {indice}: sin descripción, omitida")
				continue

			if codigo and frappe.db.exists(
				"Asset", {"codigo_bienes_nacionales": codigo, "company": self.company}
			):
				omitidos += 1
				continue

			try:
				doc = frappe.get_doc(dict(doctype="Asset", company=self.company, **datos))
				doc.flags.ignore_permissions = True
				doc.flags.ignore_mandatory = True
				doc.insert()
				creados += 1
			except Exception as error:
				errores.append(f"Fila {indice}: {error}")

		self.db_set("activos_creados", creados)
		self.db_set("estado", "Con errores" if errores else "Importado")
		self.db_set(
			"bitacora",
			"\n".join(
				[
					f"Filas leídas: {len(filas)}",
					f"Activos creados: {creados}",
					f"Omitidos por código ya existente: {omitidos}",
					f"Errores: {len(errores)}",
				]
				+ errores[:50]
			),
		)

		return {"creados": creados, "omitidos": omitidos, "errores": errores}
