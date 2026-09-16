# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Importación del Plan de Cuentas Contables de DIGECOG (Versión 2.0, junio 2023).

El plan es único y obligatorio para todo el sector público dominicano: 7 niveles,
12 dígitos, 3,595 cuentas. Ninguna institución puede crear, modificar ni eliminar
cuentas dentro de esos 7 niveles — solo DIGECOG. Una institución únicamente puede
"personalizar" ocultando las cuentas que no le apliquen, lo que es un filtro de
UI/reporte y no una eliminación de datos.

No se usa el Chart of Accounts Importer estándar de ERPNext porque espera una
jerarquía plana por `parent_account` y nombres de cuenta únicos por Company; el
plan DIGECOG repite nombres de cuenta en distintas ramas y se identifica por
código, no por nombre.
"""

import csv
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.utils.nestedset import rebuild_tree

from tz_gobierno.digecog.reparacion_csv import reparar

# Filas que trae el CSV extraído del PDF.
FILAS_CSV_DIGECOG = 3595

# Cuentas reales del plan tras reparar el defecto de extracción documentado en
# reparacion_csv.py (80 cuentas de nivel 7 que el PDF-a-CSV perdió).
TOTAL_CUENTAS_DIGECOG = 3675

# `tabAccount`.name es varchar(140) y Frappe lo arma como
# "{account_number} - {account_name} - {abbr}". Siete cuentas del plan tienen
# nombres oficiales que no caben; se trunca el account_name para el docname y el
# nombre oficial íntegro se guarda en el custom field de abajo.
LARGO_MAX_NAME = 140
CAMPO_NOMBRE_COMPLETO = "nombre_digecog_completo"

# Conteos por root_type DESPUÉS de reparar el CSV. Los del spec (Asset 1726,
# Liability 557, Equity 86, Income 555, Expense 671) suman 3,595 y corresponden al
# CSV crudo, con las 80 cuentas perdidas por la extracción del PDF.
CONTEO_POR_ROOT_TYPE = {
	"Asset": 1769,
	"Liability": 562,
	"Equity": 86,
	"Income": 585,
	"Expense": 673,
}

# Los del CSV crudo, que los tests fijan aparte para que quede constancia de que la
# diferencia es exactamente la reparación y no una deriva accidental.
CONTEO_POR_ROOT_TYPE_CSV_CRUDO = {
	"Asset": 1726,
	"Liability": 557,
	"Equity": 86,
	"Income": 555,
	"Expense": 671,
}

REPORT_TYPE_POR_ROOT_TYPE = {
	"Asset": "Balance Sheet",
	"Liability": "Balance Sheet",
	"Equity": "Balance Sheet",
	"Income": "Profit and Loss",
	"Expense": "Profit and Loss",
}


def ruta_csv():
	"""Ruta al CSV de fixtures con el plan extraído del PDF oficial de DIGECOG."""
	return os.path.join(
		os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
		"fixtures",
		"plan_de_cuentas_digecog.csv",
	)


def leer_csv(csv_path=None):
	"""Devuelve las filas del plan ordenadas por nivel ascendente.

	El orden por nivel garantiza que el padre siempre exista al momento de crear
	el hijo, sin necesidad de un segundo pase de resolución.
	"""
	with open(csv_path or ruta_csv(), encoding="utf-8") as f:
		filas = list(csv.DictReader(f))

	# El CSV trae 40 filas con el nombre corrupto por la extracción del PDF, que se
	# comieron 80 cuentas de nivel 7. Se reparan antes de cualquier otra cosa; el
	# parser es estricto y lanza si encuentra una forma que no reconoce.
	filas, _informe = reparar(filas)

	for fila in filas:
		fila["codigo"] = fila["codigo"].strip()
		fila["codigo_padre"] = (fila.get("codigo_padre") or "").strip()
		fila["nombre_cuenta"] = fila["nombre_cuenta"].strip()
		fila["nivel"] = int(fila["nivel"])
		fila["is_group"] = int(fila["is_group"])

	return sorted(filas, key=lambda f: (f["nivel"], f["codigo"]))


def resolver_padre(codigo_padre, codigos_existentes):
	"""Resuelve el código del padre, saltando huecos del documento fuente.

	El PDF oficial de DIGECOG tiene un hueco real de datos: la cuenta `4.9.99`
	("Ingresos Transitorios") declara padre `4.9`, pero `4.9` no está definida en
	ninguna parte del documento. No es un error de extracción del CSV.

	La regla aquí es genérica en vez de un caso especial para `4.9.99`: si el padre
	declarado no existe, se sube por el árbol recortando segmentos hasta encontrar
	un ancestro que sí exista. Para `4.9` eso da `4` (INGRESOS), que es el mismo
	root_type, así que la cuenta queda colgada del nivel 1 correcto.

	Se prefirió esto sobre crear un grupo intermedio `4.9` inventado porque ese
	grupo no tiene nombre oficial de DIGECOG y alteraría el conteo de cuentas del
	plan, que es lo que verifica digecog/verificacion.py.
	"""
	if not codigo_padre:
		return None

	candidato = codigo_padre
	while candidato:
		if candidato in codigos_existentes:
			return candidato
		if "." not in candidato:
			return None
		candidato = candidato.rsplit(".", 1)[0]

	return None


def asegurar_campo_nombre_completo():
	"""Custom field en Account con el nombre oficial DIGECOG sin truncar."""
	if frappe.db.exists("Custom Field", {"dt": "Account", "fieldname": CAMPO_NOMBRE_COMPLETO}):
		return
	create_custom_field(
		"Account",
		{
			"fieldname": CAMPO_NOMBRE_COMPLETO,
			"label": "Nombre DIGECOG completo",
			"fieldtype": "Small Text",
			"read_only": 1,
			"insert_after": "account_name",
			"description": "Nombre oficial íntegro del Plan de Cuentas DIGECOG. "
			"account_name puede venir truncado porque el docname de Frappe "
			"está limitado a 140 caracteres.",
		},
	)


def truncar_account_name(codigo, nombre, abbr):
	"""Recorta `nombre` para que "{codigo} - {nombre} - {abbr}" quepa en 140 chars.

	Devuelve (nombre_para_docname, fue_truncado).
	"""
	disponible = LARGO_MAX_NAME - len(codigo) - len(abbr) - len(" - ") * 2
	if len(nombre) <= disponible:
		return nombre, False
	return nombre[: disponible - 1].rstrip() + "…", True


def importar_plan_de_cuentas(company, csv_path=None, verbose=False):
	"""Crea el plan DIGECOG completo para `company`. Idempotente.

	Una cuenta ya existente se identifica por (`account_number`, `company`), que es
	la clave única real del plan — no por `account_name`, que se repite entre ramas.
	Reejecutar solo crea lo que falte.

	Devuelve un dict con el resumen: creadas, existentes, reparentadas.
	"""
	if not frappe.db.exists("Company", company):
		frappe.throw(f"La Company {company} no existe")

	asegurar_campo_nombre_completo()

	abbr = frappe.get_cached_value("Company", company, "abbr")
	filas = leer_csv(csv_path)
	codigos_csv = {f["codigo"] for f in filas}

	# account_number -> docname, precargado con lo que ya exista para idempotencia.
	mapa = dict(
		frappe.get_all(
			"Account",
			filters={"company": company},
			fields=["account_number", "name"],
			as_list=True,
		)
	)

	creadas, existentes, reparentadas, truncadas = 0, 0, [], []

	# El árbol de Account es un nested set: recalcular lft/rgt en cada insert
	# convierte 3,595 inserts en una operación cuadrática. Se difiere y se
	# reconstruye el árbol una sola vez al final.
	frappe.local.flags.ignore_update_nsm = True

	try:
		for fila in filas:
			codigo = fila["codigo"]

			if mapa.get(codigo):
				existentes += 1
				continue

			codigo_padre_real = resolver_padre(fila["codigo_padre"], codigos_csv)
			if fila["codigo_padre"] and codigo_padre_real != fila["codigo_padre"]:
				reparentadas.append((codigo, fila["codigo_padre"], codigo_padre_real))

			parent_account = mapa.get(codigo_padre_real) if codigo_padre_real else None
			if codigo_padre_real and not parent_account:
				frappe.throw(
					f"Cuenta {codigo}: el padre resuelto {codigo_padre_real} no fue creado aún. "
					"¿El CSV está desordenado por nivel?"
				)

			root_type = fila["root_type"]
			nombre_oficial = fila["nombre_cuenta"]
			nombre_docname, fue_truncado = truncar_account_name(codigo, nombre_oficial, abbr)
			if fue_truncado:
				truncadas.append(codigo)

			doc = frappe.get_doc(
				{
					"doctype": "Account",
					"company": company,
					"account_number": codigo,
					"account_name": nombre_docname,
					CAMPO_NOMBRE_COMPLETO: nombre_oficial,
					"parent_account": parent_account,
					"is_group": fila["is_group"],
					"root_type": root_type,
					"report_type": REPORT_TYPE_POR_ROOT_TYPE[root_type],
				}
			)
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.insert()

			mapa[codigo] = doc.name
			creadas += 1

			if verbose and creadas % 500 == 0:
				print(f"  {creadas} cuentas creadas...")
	finally:
		frappe.local.flags.ignore_update_nsm = False

	rebuild_tree("Account")
	frappe.db.commit()

	resumen = {
		"company": company,
		"creadas": creadas,
		"existentes": existentes,
		"reparentadas": reparentadas,
		"truncadas": truncadas,
		"total": creadas + existentes,
	}

	if verbose:
		print(f"Plan DIGECOG importado en {company}: {resumen}")

	return resumen


def crear_company_sin_coa_estandar(nombre, abbr, pais="Dominican Republic", moneda="DOP"):
	"""Crea una Company sin el plan de cuentas por defecto de ERPNext.

	`ignore_chart_of_accounts` evita que Company.on_update dispare
	create_default_accounts(); si no, ERPNext siembra su plantilla estándar y el
	plan DIGECOG quedaría mezclado con cuentas que no son del sector público
	dominicano, rompiendo el conteo de 3,595.
	"""
	if frappe.db.exists("Company", nombre):
		return frappe.get_doc("Company", nombre)

	frappe.local.flags.ignore_chart_of_accounts = True
	try:
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": nombre,
				"abbr": abbr,
				"default_currency": moneda,
				"country": pais,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
	finally:
		frappe.local.flags.ignore_chart_of_accounts = False

	frappe.db.commit()
	return company


@frappe.whitelist()
def ejecutar(company, csv_path=None):
	"""Entrypoint para `bench execute tz_gobierno.digecog.coa_import.ejecutar`."""
	return importar_plan_de_cuentas(company, csv_path=csv_path, verbose=True)
