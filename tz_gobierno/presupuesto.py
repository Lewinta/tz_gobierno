# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Subledger presupuestario público: compromiso → devengado → pagado (§4 del spec).

El `Budget` nativo de ERPNext no sirve para esto: solo compara gasto real acumulado
contra un techo, sin estados intermedios. El ciclo del sector público dominicano
necesita saber, en todo momento, cuánto está comprometido pero aún no devengado —
porque la disponibilidad presupuestaria que se valida al emitir una orden de compra
depende justamente de ese estado intermedio.

MODELO DE MOVIMIENTOS
---------------------
Cada `Movimiento Presupuestario` suma en una sola etapa, siempre con monto positivo.
Un reverso nunca es un monto negativo sobre la etapa original: es una fila propia con
`etapa="Reversado"` y `etapa_revertida=<la etapa que anula>`. Así el ledger conserva
la traza de qué pasó y cuándo, que es lo que audita la Contraloría.

Una transición de etapa son dos filas: liberar la anterior y cargar la siguiente. Al
devengar una factura que venía de una orden de compra se emite
`Reversado(revertida=Comprometido)` + `Devengado`.

Los saldos vivos se derivan del ledger, nunca se acumulan de forma incremental:

    comprometido = Σ Comprometido − Σ Reversado(revertida=Comprometido)
    devengado    = Σ Devengado    − Σ Reversado(revertida=Devengado)
    pagado       = Σ Pagado       − Σ Reversado(revertida=Pagado)

DISPONIBILIDAD
--------------
El §4.1 del spec define `disponible = monto_modificado − monto_comprometido`, pero el
§4.3 dice que devengar *reduce* el comprometido. Las dos reglas juntas son
inconsistentes: al facturar una orden, el comprometido baja a cero y la disponibilidad
volvería al monto completo, como si el dinero nunca se hubiera gastado.

Se implementa la que es correcta contablemente:

    disponible = monto_modificado − comprometido − devengado − pagado

BASE DE MONTOS
--------------
Se usa `base_net_amount` (moneda de la institución, sin impuestos) porque el control
es por cuenta contable y los impuestos se imputan a su propia cuenta — el ITBIS
adelantado consume la línea presupuestaria de la cuenta de ITBIS, no la del gasto.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

ROL_OVERRIDE = "Presupuesto Override"

ETAPA_COMPROMETIDO = "Comprometido"
ETAPA_DEVENGADO = "Devengado"
ETAPA_PAGADO = "Pagado"
ETAPA_REVERSADO = "Reversado"

CAMPO_POR_ETAPA = {
	ETAPA_COMPROMETIDO: "monto_comprometido",
	ETAPA_DEVENGADO: "monto_devengado",
	ETAPA_PAGADO: "monto_pagado",
}


# --------------------------------------------------------------------------- #
# Resolución de líneas y recálculo de saldos
# --------------------------------------------------------------------------- #


def fiscal_year_de(fecha, company):
	from erpnext.accounts.utils import get_fiscal_year

	return get_fiscal_year(getdate(fecha), company=company, as_dict=True).name


def resolver_linea(company, fiscal_year, account, cost_center, project=None):
	"""Devuelve el nombre de la Linea Presupuestaria que aplica, o None.

	El proyecto es opcional en la línea: primero se busca la línea específica del
	proyecto y, si no existe, la línea general de esa cuenta y centro de costo. Así
	una institución puede presupuestar por programa sin tener que abrir una línea por
	proyecto para cada cuenta.
	"""
	base = {
		"company": company,
		"fiscal_year": fiscal_year,
		"account": account,
		"cost_center": cost_center,
	}

	if project:
		especifica = frappe.db.get_value("Linea Presupuestaria", dict(base, project=project))
		if especifica:
			return especifica

	return frappe.db.get_value("Linea Presupuestaria", dict(base, project=["in", ["", None]]))


def saldos_de_linea(linea):
	"""Recalcula los saldos desde el ledger de movimientos. Fuente de verdad."""
	filas = frappe.db.sql(
		"""
		select etapa, ifnull(etapa_revertida, '') as etapa_revertida, sum(monto) as total
		from `tabMovimiento Presupuestario`
		where linea_presupuestaria = %s
		group by etapa, ifnull(etapa_revertida, '')
		""",
		linea,
		as_dict=True,
	)

	saldos = {ETAPA_COMPROMETIDO: 0.0, ETAPA_DEVENGADO: 0.0, ETAPA_PAGADO: 0.0}

	for fila in filas:
		if fila.etapa == ETAPA_REVERSADO:
			if fila.etapa_revertida in saldos:
				saldos[fila.etapa_revertida] -= flt(fila.total)
		elif fila.etapa in saldos:
			saldos[fila.etapa] += flt(fila.total)

	return saldos


def recalcular(linea):
	"""Persiste en la Linea Presupuestaria los saldos derivados del ledger."""
	saldos = saldos_de_linea(linea)
	doc = frappe.get_doc("Linea Presupuestaria", linea)

	doc.monto_comprometido = saldos[ETAPA_COMPROMETIDO]
	doc.monto_devengado = saldos[ETAPA_DEVENGADO]
	doc.monto_pagado = saldos[ETAPA_PAGADO]
	doc.disponible = (
		flt(doc.monto_modificado)
		- flt(doc.monto_comprometido)
		- flt(doc.monto_devengado)
		- flt(doc.monto_pagado)
	)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_validate_update_after_submit = True
	doc.save()
	return doc


def _crear_movimiento(
	linea, fecha, etapa, monto, doc_origen, etapa_revertida=None, observaciones=None, disparador=None
):
	"""Registra un movimiento.

	`doc_origen` es el documento **cuyo saldo se afecta**, no necesariamente el que
	provocó el movimiento. Al devengar una factura que venía de una orden de compra,
	la liberación del compromiso afecta a la ORDEN (es su compromiso el que baja) pero
	la dispara la FACTURA — eso va en `disparador`.

	La distinción no es cosmética: `_movimientos_vivos()` calcula cuánto tiene todavía
	cargado un documento en una etapa, y si la liberación se anotara contra la factura,
	la orden seguiría pareciendo comprometida y al cancelarla se revertiría dos veces.
	"""
	if flt(monto) <= 0:
		return None

	mov = frappe.get_doc(
		{
			"doctype": "Movimiento Presupuestario",
			"linea_presupuestaria": linea,
			"fecha": fecha,
			"etapa": etapa,
			"etapa_revertida": etapa_revertida,
			"monto": flt(monto),
			"referencia_doctype": doc_origen.doctype,
			"referencia_name": doc_origen.name,
			"disparador_doctype": disparador.doctype if disparador else None,
			"disparador_name": disparador.name if disparador else None,
			"observaciones": observaciones,
		}
	)
	mov.flags.ignore_permissions = True
	mov.insert()
	return mov


# --------------------------------------------------------------------------- #
# Desglose de documentos en líneas presupuestarias
# --------------------------------------------------------------------------- #


def _lineas_de_items(doc, fecha):
	"""Mapea los items de una PO/PI a (linea, monto). Agrega los que caen en la misma.

	Devuelve (mapa, sin_linea) donde `sin_linea` lista los items que no encontraron
	línea presupuestaria, para que el llamador decida si eso es un error.
	"""
	fiscal_year = fiscal_year_de(fecha, doc.company)
	mapa, sin_linea = {}, []

	for item in doc.items:
		if not item.expense_account:
			sin_linea.append((item.idx, None, "el item no tiene cuenta de gasto"))
			continue

		linea = resolver_linea(
			doc.company, fiscal_year, item.expense_account, item.cost_center, item.get("project")
		)
		if not linea:
			sin_linea.append((item.idx, item.expense_account, "no hay línea presupuestaria"))
			continue

		mapa[linea] = mapa.get(linea, 0.0) + flt(item.base_net_amount)

	return mapa, sin_linea


def _usuario_puede_exceder():
	return ROL_OVERRIDE in frappe.get_roles()


# --------------------------------------------------------------------------- #
# Hooks: Purchase Order → Comprometido
# --------------------------------------------------------------------------- #


def validar_disponibilidad(doc, method=None):
	"""Bloquea la emisión de una orden de compra que exceda la disponibilidad.

	Es el control que pide el pliego "por centro de costo, programa o proyecto", y
	es lo que un perito probará en la demo creando una OC por encima del presupuesto.

	Un usuario con el rol `Presupuesto Override` solo recibe advertencia — el sector
	público necesita esa válvula para casos de modificación presupuestaria en trámite,
	pero queda registrada en el documento.
	"""
	mapa, _sin_linea = _lineas_de_items(doc, doc.transaction_date)
	excesos = []

	for linea, monto in mapa.items():
		lp = frappe.db.get_value(
			"Linea Presupuestaria", linea, ["account", "cost_center", "disponible"], as_dict=True
		)
		if flt(monto) > flt(lp.disponible):
			excesos.append(
				_("{0} / {1}: solicitado {2}, disponible {3}").format(
					lp.account, lp.cost_center, frappe.format_value(monto, "Currency"),
					frappe.format_value(lp.disponible, "Currency"),
				)
			)

	if not excesos:
		return

	detalle = "<br>".join(excesos)
	if _usuario_puede_exceder():
		frappe.msgprint(
			_("Se excede la disponibilidad presupuestaria:<br>{0}").format(detalle),
			title=_("Presupuesto excedido"),
			indicator="orange",
		)
	else:
		frappe.throw(
			_("No hay disponibilidad presupuestaria:<br>{0}").format(detalle),
			title=_("Presupuesto insuficiente"),
		)


def registrar_compromiso(doc, method=None):
	mapa, _sin_linea = _lineas_de_items(doc, doc.transaction_date)
	for linea, monto in mapa.items():
		_crear_movimiento(linea, doc.transaction_date, ETAPA_COMPROMETIDO, monto, doc)
		recalcular(linea)


def revertir_compromiso(doc, method=None):
	"""Libera el compromiso pendiente al cancelar la orden.

	Solo se revierte lo que sigue comprometido: si la orden ya se facturó, ese tramo
	pasó a devengado y lo revierte la cancelación de la factura, no esta.
	"""
	for linea, monto in _movimientos_vivos(doc, ETAPA_COMPROMETIDO).items():
		_crear_movimiento(
			linea, doc.transaction_date, ETAPA_REVERSADO, monto, doc,
			etapa_revertida=ETAPA_COMPROMETIDO,
			observaciones=_("Reverso por cancelación de {0}").format(doc.name),
		)
		recalcular(linea)


def _movimientos_vivos(doc, etapa):
	"""Monto que este documento aún tiene cargado en `etapa`, por línea.

	Es lo cargado por el documento menos lo que ya se le revirtió, para no revertir
	dos veces ni revertir un tramo que ya transicionó a la etapa siguiente.
	"""
	filas = frappe.db.sql(
		"""
		select linea_presupuestaria,
		       sum(case when etapa = %(etapa)s then monto else 0 end)
		     - sum(case when etapa = %(reversado)s and etapa_revertida = %(etapa)s
		                then monto else 0 end) as vivo
		from `tabMovimiento Presupuestario`
		where referencia_doctype = %(dt)s and referencia_name = %(dn)s
		group by linea_presupuestaria
		""",
		{
			"etapa": etapa,
			"reversado": ETAPA_REVERSADO,
			"dt": doc.doctype,
			"dn": doc.name,
		},
		as_dict=True,
	)
	return {f.linea_presupuestaria: flt(f.vivo) for f in filas if flt(f.vivo) > 0}


# --------------------------------------------------------------------------- #
# Hooks: Purchase Invoice → Devengado
# --------------------------------------------------------------------------- #


def registrar_devengado(doc, method=None):
	"""Devenga la factura, liberando el compromiso de la orden que la originó.

	Si la factura no referencia una orden de compra (compra directa sin compromiso
	previo) se devenga directo y se marca en `observaciones`, para que el reporte de
	auditoría pueda destacar ese caso — que en el sector público es una excepción.
	"""
	mapa, _sin_linea = _lineas_de_items(doc, doc.posting_date)
	compromiso_por_linea = _compromiso_de_ordenes(doc)

	for linea, monto in mapa.items():
		disponible_a_liberar = compromiso_por_linea.get(linea) or {}
		por_liberar = min(flt(monto), flt(disponible_a_liberar.get("monto", 0.0)))

		if por_liberar > 0:
			orden = disponible_a_liberar["orden"]
			_crear_movimiento(
				linea, doc.posting_date, ETAPA_REVERSADO, por_liberar, orden,
				etapa_revertida=ETAPA_COMPROMETIDO,
				disparador=doc,
				observaciones=_("Transición a devengado por {0}").format(doc.name),
			)

		observaciones = None if por_liberar >= flt(monto) else _("Devengado sin compromiso previo")
		_crear_movimiento(
			linea, doc.posting_date, ETAPA_DEVENGADO, monto, doc, observaciones=observaciones
		)
		recalcular(linea)


def _compromiso_de_ordenes(doc):
	"""Compromiso vivo, por línea, de las órdenes que esta factura referencia.

	Devuelve {linea: {"monto": x, "orden": <doc Purchase Order>}}. Se conserva la
	orden porque la liberación del compromiso hay que anotarla contra ella.
	"""
	ordenes = {item.purchase_order for item in doc.items if item.get("purchase_order")}
	total = {}

	for nombre in ordenes:
		po = frappe.get_doc("Purchase Order", nombre)
		for linea, monto in _movimientos_vivos(po, ETAPA_COMPROMETIDO).items():
			if linea in total:
				total[linea]["monto"] += monto
			else:
				total[linea] = {"monto": monto, "orden": po}

	return total


def revertir_devengado(doc, method=None):
	"""Anula el devengado y devuelve a comprometido lo que esta factura había liberado.

	La orden de compra sigue viva tras anular su factura, así que su compromiso tiene
	que volver a aparecer: si no, quedaría presupuesto disponible que en realidad está
	comprometido por una orden abierta.
	"""
	for linea, monto in _movimientos_vivos(doc, ETAPA_DEVENGADO).items():
		_crear_movimiento(
			linea, doc.posting_date, ETAPA_REVERSADO, monto, doc,
			etapa_revertida=ETAPA_DEVENGADO,
			observaciones=_("Reverso por cancelación de {0}").format(doc.name),
		)
		recalcular(linea)

	for liberacion in _liberaciones_disparadas_por(doc):
		orden = frappe._dict(
			doctype=liberacion.referencia_doctype, name=liberacion.referencia_name
		)
		_crear_movimiento(
			liberacion.linea_presupuestaria, doc.posting_date, ETAPA_COMPROMETIDO,
			liberacion.monto, orden,
			disparador=doc,
			observaciones=_("Compromiso restituido al anularse {0}").format(doc.name),
		)
		recalcular(liberacion.linea_presupuestaria)


def _liberaciones_disparadas_por(doc):
	"""Liberaciones de compromiso que este documento provocó y siguen en pie."""
	return frappe.db.sql(
		"""
		select linea_presupuestaria, referencia_doctype, referencia_name, sum(monto) as monto
		from `tabMovimiento Presupuestario`
		where disparador_doctype = %(dt)s
		  and disparador_name = %(dn)s
		  and etapa = %(reversado)s
		  and etapa_revertida = %(comprometido)s
		group by linea_presupuestaria, referencia_doctype, referencia_name
		""",
		{
			"dt": doc.doctype,
			"dn": doc.name,
			"reversado": ETAPA_REVERSADO,
			"comprometido": ETAPA_COMPROMETIDO,
		},
		as_dict=True,
	)


# --------------------------------------------------------------------------- #
# Hooks: Payment Entry → Pagado
# --------------------------------------------------------------------------- #


def registrar_pagado(doc, method=None):
	"""Pasa de devengado a pagado el monto que este pago salda de cada factura.

	El pago se asigna a la factura completa, no línea por línea, así que se reparte
	a prorrata entre las líneas presupuestarias de esa factura.
	"""
	for factura, asignado in _facturas_pagadas(doc).items():
		devengado_vivo = _movimientos_vivos_de(
			"Purchase Invoice", factura, ETAPA_DEVENGADO
		)
		total_vivo = sum(devengado_vivo.values())
		if total_vivo <= 0:
			continue

		proporcion = min(flt(asignado) / total_vivo, 1.0)

		for linea, monto_vivo in devengado_vivo.items():
			monto = flt(monto_vivo) * proporcion
			_crear_movimiento(
				linea, doc.posting_date, ETAPA_REVERSADO, monto, doc,
				etapa_revertida=ETAPA_DEVENGADO,
				observaciones=_("Transición a pagado por {0}").format(doc.name),
			)
			_crear_movimiento(linea, doc.posting_date, ETAPA_PAGADO, monto, doc)
			recalcular(linea)


def _facturas_pagadas(doc):
	facturas = {}
	for ref in doc.get("references") or []:
		if ref.reference_doctype != "Purchase Invoice":
			continue
		facturas[ref.reference_name] = facturas.get(ref.reference_name, 0.0) + flt(
			ref.allocated_amount
		)
	return facturas


def _movimientos_vivos_de(doctype, name, etapa):
	fake = frappe._dict(doctype=doctype, name=name)
	return _movimientos_vivos(fake, etapa)


def revertir_pagado(doc, method=None):
	for linea, monto in _movimientos_vivos(doc, ETAPA_PAGADO).items():
		_crear_movimiento(
			linea, doc.posting_date, ETAPA_REVERSADO, monto, doc,
			etapa_revertida=ETAPA_PAGADO,
			observaciones=_("Reverso por cancelación de {0}").format(doc.name),
		)
		# Al deshacer el pago, el monto vuelve a estar devengado.
		_crear_movimiento(
			linea, doc.posting_date, ETAPA_DEVENGADO, monto, doc,
			observaciones=_("Retorno a devengado por cancelación de {0}").format(doc.name),
		)
		recalcular(linea)
