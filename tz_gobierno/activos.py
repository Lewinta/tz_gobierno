# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Etiquetas de activos con QR y código de Bienes Nacionales (§7 del spec).

El QR se genera como SVG inline con `pyqrcode`, que el bench ya trae instalado: no se
agrega ninguna dependencia nueva ni se llama a un servicio externo de generación de
códigos, porque la etiqueta se tiene que poder imprimir con el sistema desconectado
de internet (el pliego especifica uso off-line).
"""

import io

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

CAMPO_BIENES_NACIONALES = "codigo_bienes_nacionales"


def asegurar_campo_bienes_nacionales():
	"""Agrega a Asset el código de Bienes Nacionales, que es el que audita el Estado."""
	if frappe.db.exists("Custom Field", {"dt": "Asset", "fieldname": CAMPO_BIENES_NACIONALES}):
		return False

	create_custom_field(
		"Asset",
		{
			"fieldname": CAMPO_BIENES_NACIONALES,
			"label": "Código de Bienes Nacionales",
			"fieldtype": "Data",
			"insert_after": "asset_name",
			"unique": 1,
			"description": "Código asignado por la Dirección General de Bienes Nacionales. "
			"Es el identificador con el que el activo se audita, distinto del "
			"nombre interno de ERPNext.",
		},
	)
	return True


def qr_svg(texto, tamano=90):
	"""SVG del QR, listo para incrustar en un Print Format.

	Devuelve cadena vacía si el texto viene vacío: una etiqueta sin código es válida
	(el activo puede estar pendiente de registrar en Bienes Nacionales), solo que sin QR.
	"""
	if not texto:
		return ""

	import pyqrcode

	buffer = io.BytesIO()
	# xmldecl=False para poder incrustarlo dentro del HTML del Print Format sin que
	# quede una declaración XML en medio del documento.
	pyqrcode.create(texto, error="M").svg(
		buffer, scale=3, xmldecl=False, svgns=True, omithw=True, quiet_zone=1
	)
	svg = buffer.getvalue().decode("utf-8")
	return svg.replace("<svg ", f'<svg width="{tamano}" height="{tamano}" ', 1)


@frappe.whitelist()
def datos_etiqueta(asset):
	"""Datos que consume el Print Format de la etiqueta."""
	doc = frappe.get_doc("Asset", asset)
	codigo = doc.get(CAMPO_BIENES_NACIONALES) or doc.name

	return {
		"asset": doc.name,
		"asset_name": doc.asset_name,
		"codigo_bienes_nacionales": doc.get(CAMPO_BIENES_NACIONALES),
		"company": doc.company,
		"location": doc.get("location"),
		"custodian": doc.get("custodian"),
		"qr": qr_svg(codigo),
	}


def instalar():
	"""Se llama desde after_migrate para que el campo exista en cualquier sitio."""
	creado = asegurar_campo_bienes_nacionales()
	if creado:
		frappe.db.commit()
	return creado
