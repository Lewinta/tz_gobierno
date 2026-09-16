# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Verificación de integridad del plan de cuentas DIGECOG importado.

La cláusula 16.1.1 del pliego CES-DAF-CM-2026-0009 es excluyente: un submódulo no
conforme descalifica la oferta. Este módulo existe para poder demostrar, en vivo y
con números, que el plan importado es exactamente el oficial.
"""

import frappe

from tz_gobierno.digecog.coa_import import CONTEO_POR_ROOT_TYPE, TOTAL_CUENTAS_DIGECOG


def resumen_plan(company):
	"""Devuelve conteos del plan importado para `company`, listo para comparar."""
	total = frappe.db.count("Account", {"company": company})

	# Frappe v16 rechaza funciones SQL como string en get_all(fields=...),
	# así que el conteo agrupado va por SQL directo.
	por_root_type = dict(
		frappe.db.sql(
			"""
			select root_type, count(name)
			from `tabAccount`
			where company = %s and ifnull(root_type, '') != ''
			group by root_type
			""",
			company,
		)
	)

	huerfanas = frappe.db.sql(
		"""
		select count(*)
		from `tabAccount` hijo
		where hijo.company = %s
		  and ifnull(hijo.parent_account, '') != ''
		  and not exists (
			select 1 from `tabAccount` padre where padre.name = hijo.parent_account
		  )
		""",
		company,
	)[0][0]

	raices = frappe.db.count("Account", {"company": company, "parent_account": ["in", ["", None]]})

	return {
		"company": company,
		"total": total,
		"total_esperado": TOTAL_CUENTAS_DIGECOG,
		"por_root_type": por_root_type,
		"por_root_type_esperado": CONTEO_POR_ROOT_TYPE,
		"huerfanas": huerfanas,
		"raices": raices,
		"conforme": (
			total == TOTAL_CUENTAS_DIGECOG
			and por_root_type == CONTEO_POR_ROOT_TYPE
			and huerfanas == 0
		),
	}


@frappe.whitelist()
def imprimir_resumen(company):
	"""Entrypoint legible para `bench execute`."""
	r = resumen_plan(company)
	print(f"Company: {r['company']}")
	print(f"  total cuentas : {r['total']} (esperado {r['total_esperado']})")
	for rt, esperado in sorted(r["por_root_type_esperado"].items()):
		real = r["por_root_type"].get(rt, 0)
		print(f"  {rt:10}    : {real:5} (esperado {esperado:5}) {'OK' if real == esperado else '<-- DIFIERE'}")
	print(f"  huerfanas     : {r['huerfanas']}")
	print(f"  raices        : {r['raices']}")
	print(f"  CONFORME      : {r['conforme']}")
	return r
