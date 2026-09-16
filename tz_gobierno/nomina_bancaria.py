# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Generación del archivo de nómina electrónica bancaria (§8 del spec).

El layout exacto del archivo lo entrega el banco directamente al cliente
institucional; no está publicado. En vez de esperar ese documento y quedarnos sin
módulo, el formato se define por configuración: `Banco Nomina Config` describe qué
campo va en qué columna, con qué ancho y qué relleno, y este módulo lo materializa.

Cuando llegue el layout real de Banreservas será cuestión de editar un registro, no
de reprogramar. Un registro cuyo `verificado` esté sin marcar produce igualmente el
archivo, pero se advierte que es una aproximación no confirmada por el banco.
"""

import csv
import io
from xml.sax.saxutils import escape

import frappe
from frappe import _
from frappe.utils import flt

CAMPO_CUENTA = "Cuenta bancaria del empleado"
CAMPO_CEDULA = "Cédula"
CAMPO_NOMBRE = "Nombre completo"
CAMPO_MONTO = "Monto neto"
CAMPO_BANCO = "Código de banco"
CAMPO_TIPO_CUENTA = "Tipo de cuenta"
CAMPO_FIJO = "Texto fijo"


def datos_de_nomina(payroll_entry):
	"""Una fila por empleado pagado en la corrida, con lo que pide cualquier banco."""
	filas = frappe.db.sql(
		"""
		select ss.employee, ss.employee_name, ss.net_pay,
		       e.bank_ac_no, e.bank_name, e.ifsc_code
		from `tabSalary Slip` ss
		join `tabEmployee` e on e.name = ss.employee
		where ss.payroll_entry = %s and ss.docstatus = 1
		order by ss.employee_name
		""",
		payroll_entry,
		as_dict=True,
	)

	for fila in filas:
		fila["cedula"] = _cedula_de(fila.employee)

	return filas


def _cedula_de(employee):
	"""Cédula del empleado.

	ERPNext no tiene un campo de cédula dominicana; las instituciones suelen usar
	`custom_cedula` o el genérico `personal_email`/`passport_number`. Se busca en ese
	orden y se devuelve vacío si no hay ninguno, en vez de inventar un valor.
	"""
	doc = frappe.get_doc("Employee", employee)
	for campo in ("custom_cedula", "cedula", "passport_number", "person_number"):
		valor = doc.get(campo)
		if valor:
			return str(valor)
	return ""


def _valor_de_columna(columna, fila):
	campo = columna.campo

	if campo == CAMPO_CUENTA:
		return fila.get("bank_ac_no") or ""
	if campo == CAMPO_CEDULA:
		return fila.get("cedula") or ""
	if campo == CAMPO_NOMBRE:
		return fila.get("employee_name") or ""
	if campo == CAMPO_MONTO:
		return f"{flt(fila.get('net_pay')):.2f}"
	if campo == CAMPO_BANCO:
		return fila.get("ifsc_code") or fila.get("bank_name") or ""
	if campo == CAMPO_TIPO_CUENTA:
		return columna.valor_fijo or ""
	if campo == CAMPO_FIJO:
		return columna.valor_fijo or ""

	return ""


def _ajustar(valor, columna):
	"""Aplica ancho y relleno, para los formatos de ancho fijo."""
	ancho = int(columna.ancho or 0)
	if not ancho:
		return valor

	valor = valor[:ancho]
	if (columna.relleno or "Izquierda") == "Izquierda":
		return valor.rjust(ancho)
	return valor.ljust(ancho)


def generar(payroll_entry, banco_config):
	"""Devuelve (nombre_de_archivo, contenido) del archivo de nómina.

	Lanza si la configuración no tiene columnas: generar un archivo vacío que el banco
	rechaza es peor que fallar aquí con un mensaje claro.
	"""
	config = frappe.get_doc("Banco Nomina Config", banco_config)
	if not config.columnas:
		frappe.throw(
			_("La configuración {0} no define ninguna columna.").format(banco_config)
		)

	filas = datos_de_nomina(payroll_entry)
	if not filas:
		frappe.throw(
			_("La corrida {0} no tiene volantes de pago confirmados.").format(payroll_entry)
		)

	columnas = sorted(config.columnas, key=lambda c: int(c.posicion or 0))

	if config.formato_archivo == "CSV":
		contenido = _generar_csv(filas, columnas, config.delimitador or ",")
	elif config.formato_archivo == "XML":
		contenido = _generar_xml(filas, columnas, config)
	else:
		contenido = _generar_ancho_fijo(filas, columnas)

	extension = (config.extension or "txt").lstrip(".")
	nombre = f"nomina-{frappe.scrub(config.banco)}-{payroll_entry}.{extension}"

	if not config.verificado:
		frappe.msgprint(
			_(
				"El layout de {0} todavía no está confirmado por el banco. El archivo se "
				"generó con la configuración actual, pero verifíquelo antes de enviarlo."
			).format(config.banco),
			title=_("Layout no verificado"),
			indicator="orange",
		)

	return nombre, contenido


def _generar_csv(filas, columnas, delimitador):
	buffer = io.StringIO()
	escritor = csv.writer(buffer, delimiter=delimitador, lineterminator="\r\n")
	for fila in filas:
		escritor.writerow([_valor_de_columna(c, fila) for c in columnas])
	return buffer.getvalue()


def _generar_ancho_fijo(filas, columnas):
	lineas = []
	for fila in filas:
		lineas.append("".join(_ajustar(_valor_de_columna(c, fila), c) for c in columnas))
	return "\r\n".join(lineas) + "\r\n"


def _generar_xml(filas, columnas, config):
	partes = ['<?xml version="1.0" encoding="UTF-8"?>', "<nomina>"]
	partes.append(f"  <banco>{escape(config.banco)}</banco>")
	partes.append("  <pagos>")
	for fila in filas:
		partes.append("    <pago>")
		for columna in columnas:
			etiqueta = frappe.scrub(columna.campo)
			partes.append(
				f"      <{etiqueta}>{escape(_valor_de_columna(columna, fila))}</{etiqueta}>"
			)
		partes.append("    </pago>")
	partes.append("  </pagos>")
	partes.append("</nomina>")
	return "\n".join(partes) + "\n"


@frappe.whitelist()
def generar_y_adjuntar(payroll_entry, banco_config):
	"""Genera el archivo y lo adjunta a la corrida de nómina.

	Se adjunta en vez de descargarse directo para que quede traza de qué archivo se
	envió al banco y cuándo — es lo que va a pedir una auditoría.
	"""
	nombre, contenido = generar(payroll_entry, banco_config)

	archivo = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": nombre,
			"attached_to_doctype": "Payroll Entry",
			"attached_to_name": payroll_entry,
			"content": contenido,
			"is_private": 1,
		}
	)
	archivo.flags.ignore_permissions = True
	archivo.insert()

	return {"file_url": archivo.file_url, "file_name": nombre}
