# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Motor de los 5 Estados Financieros oficiales de DIGECOG (§5 del spec).

Los cinco estados comparten la misma mecánica: tomar saldos del `GL Entry` estándar
de ERPNext, agruparlos por cuenta y reclasificarlos a los rubros del modelo oficial
usando `digecog/mapeo.py`. Lo que cambia entre estados es el período (saldo acumulado
vs. movimiento del período), el signo y el layout.

No se usa el Trial Balance nativo como reporte final: sirve para totalizar por cuenta,
pero el formato que exige DIGECOG es fijo y sus rubros no existen en ERPNext.

SIGNOS
------
Se normaliza todo a "positivo = saldo natural del rubro": los activos y gastos por
débito, los pasivos, patrimonio e ingresos por crédito. Así el modelo oficial se
imprime sin signos negativos salvo donde el propio modelo los pide (los gastos totales
entre paréntesis en el Estado de Rendimiento Financiero).
"""

import frappe
from frappe.utils import add_days, flt, getdate

from tz_gobierno.digecog import mapeo

# root_type cuyo saldo natural es crédito.
ROOT_TYPES_CREDITO = ("Liability", "Equity", "Income")


def saldos_por_cuenta(company, hasta, desde=None):
	"""Saldos por número de cuenta, ya normalizados a signo natural.

	Sin `desde` devuelve el saldo acumulado hasta `hasta` (Estado de Situación
	Financiera); con `desde` devuelve el movimiento del período (Rendimiento
	Financiero, Flujo de Efectivo).
	"""
	condiciones = ["gl.company = %(company)s", "gl.is_cancelled = 0", "gl.posting_date <= %(hasta)s"]
	params = {"company": company, "hasta": getdate(hasta)}

	if desde:
		condiciones.append("gl.posting_date >= %(desde)s")
		params["desde"] = getdate(desde)

	filas = frappe.db.sql(
		f"""
		select a.account_number as codigo, a.root_type as root_type,
		       sum(gl.debit) - sum(gl.credit) as saldo
		from `tabGL Entry` gl
		join `tabAccount` a on a.name = gl.account
		where {' and '.join(condiciones)}
		group by a.account_number, a.root_type
		""",
		params,
		as_dict=True,
	)

	saldos = {}
	for fila in filas:
		monto = flt(fila.saldo)
		if fila.root_type in ROOT_TYPES_CREDITO:
			monto = -monto
		saldos[fila.codigo] = saldos.get(fila.codigo, 0.0) + monto

	return saldos


def filtrar_clases(saldos, clases):
	"""Deja solo las cuentas cuya clase (primer dígito del código) esté en `clases`.

	Cada estado cubre unas clases concretas: el Estado de Situación Financiera las
	1-2-3 y el de Rendimiento Financiero las 4-5. Sin este filtro, las cuentas de
	resultado aparecerían como "sin mapear" en el balance y al revés — un falso
	positivo que ahogaría los huecos reales del mapeo.
	"""
	return {c: m for c, m in saldos.items() if c and c[0] in clases}


def agregar_por_rubro(saldos, tabla):
	"""Reclasifica {codigo: monto} a {rubro: monto} según la tabla de mapeo.

	Devuelve (por_rubro, sin_mapear). `sin_mapear` lista los códigos con saldo que
	ninguna entrada del mapeo cubre: es un hueco real del mapeo y hay que verlo, no
	silenciarlo — una cuenta con saldo que no aparece en ningún rubro descuadra el
	estado.
	"""
	por_rubro, sin_mapear = {}, []

	for codigo, monto in saldos.items():
		if not flt(monto):
			continue
		rubro, _seccion = mapeo.resolver(codigo, tabla)
		if not rubro:
			sin_mapear.append((codigo, monto))
			continue
		por_rubro[rubro] = por_rubro.get(rubro, 0.0) + flt(monto)

	return por_rubro, sin_mapear


# --------------------------------------------------------------------------- #
# Construcción de filas
# --------------------------------------------------------------------------- #


def _fila(concepto, actual=None, anterior=None, nivel=0, es_total=False):
	return {
		"concepto": concepto,
		"monto_actual": flt(actual) if actual is not None else None,
		"monto_anterior": flt(anterior) if anterior is not None else None,
		"indent": nivel,
		"es_total": 1 if es_total else 0,
	}


def _periodo_anterior(desde, hasta):
	"""Mismo período del ejercicio anterior, como exige el comparativo del manual."""
	d, h = getdate(desde) if desde else None, getdate(hasta)
	hasta_ant = h.replace(year=h.year - 1)
	desde_ant = d.replace(year=d.year - 1) if d else None
	return desde_ant, hasta_ant


# --------------------------------------------------------------------------- #
# 5.1 Estado de Situación Financiera
# --------------------------------------------------------------------------- #


def situacion_financiera(company, as_on_date, comparativo=False):
	"""Balance General en el formato oficial de DIGECOG."""

	def rubros_de(fecha):
		saldos = filtrar_clases(saldos_por_cuenta(company, fecha), "123")
		por_rubro, sin_mapear = agregar_por_rubro(saldos, mapeo.SITUACION_FINANCIERA)
		# El resultado del período no sale de una cuenta de patrimonio: es el
		# ahorro/desahorro del ejercicio, que todavía no se ha capitalizado.
		por_rubro[mapeo.RUBRO_RESULTADO_DEL_PERIODO] = resultado_del_periodo(company, fecha)
		return por_rubro, sin_mapear

	actual, sin_mapear = rubros_de(as_on_date)
	anterior = rubros_de(_periodo_anterior(None, as_on_date)[1])[0] if comparativo else {}

	filas = []
	totales = {}

	for seccion, rubros in mapeo.ORDEN_SITUACION_FINANCIERA:
		filas.append(_fila(seccion, nivel=1))
		suma_actual = suma_anterior = 0.0

		for rubro in rubros:
			a, b = flt(actual.get(rubro)), flt(anterior.get(rubro))
			suma_actual += a
			suma_anterior += b
			filas.append(_fila(rubro, a, b if comparativo else None, nivel=2))

		filas.append(_fila(f"Total {seccion.lower()}", suma_actual,
		                   suma_anterior if comparativo else None, nivel=1, es_total=True))
		totales[seccion] = (suma_actual, suma_anterior)

	def agregado(*secciones):
		return (
			sum(totales[s][0] for s in secciones),
			sum(totales[s][1] for s in secciones),
		)

	ta, tb = agregado(mapeo.ACTIVO_CORRIENTE, mapeo.ACTIVO_NO_CORRIENTE)
	filas.append(_fila("Total activos", ta, tb if comparativo else None, es_total=True))

	pa, pb = agregado(mapeo.PASIVO_CORRIENTE, mapeo.PASIVO_NO_CORRIENTE)
	filas.append(_fila("Total pasivos", pa, pb if comparativo else None, es_total=True))

	na, nb = totales[mapeo.PATRIMONIO]
	filas.append(_fila("Total activos netos/patrimonio", na, nb if comparativo else None,
	                   es_total=True))

	return filas, sin_mapear


def cuadra_situacion_financiera(filas):
	"""Total activos == Total pasivos + Total patrimonio, con tolerancia de redondeo.

	Es la prueba de integridad contable del estado: si no cuadra, o falta un rubro en
	el mapeo o hay asientos descuadrados.
	"""

	def valor(concepto):
		for fila in filas:
			if fila["concepto"] == concepto:
				return flt(fila["monto_actual"])
		return 0.0

	activos = valor("Total activos")
	pasivos_patrimonio = valor("Total pasivos") + valor("Total activos netos/patrimonio")
	return abs(activos - pasivos_patrimonio) < 0.01


# --------------------------------------------------------------------------- #
# 5.2 Estado de Rendimiento Financiero
# --------------------------------------------------------------------------- #


def rendimiento_financiero(company, desde, hasta, comparativo=False):
	"""Estado de Ahorro/Desahorro en el formato oficial."""

	def rubros_de(d, h):
		saldos = filtrar_clases(saldos_por_cuenta(company, h, desde=d), "45")
		return agregar_por_rubro(saldos, mapeo.RENDIMIENTO_FINANCIERO)

	actual, sin_mapear = rubros_de(desde, hasta)
	d_ant, h_ant = _periodo_anterior(desde, hasta)
	anterior = rubros_de(d_ant, h_ant)[0] if comparativo else {}

	filas = []
	totales = {}

	for seccion, rubros in mapeo.ORDEN_RENDIMIENTO_FINANCIERO:
		if seccion == mapeo.RESULTADOS_APARTE:
			continue

		filas.append(_fila(seccion, nivel=1))
		suma_actual = suma_anterior = 0.0

		for rubro in rubros:
			a, b = flt(actual.get(rubro)), flt(anterior.get(rubro))
			suma_actual += a
			suma_anterior += b
			filas.append(_fila(rubro, a, b if comparativo else None, nivel=2))

		etiqueta = f"Total {seccion.lower()}"
		filas.append(_fila(etiqueta, suma_actual, suma_anterior if comparativo else None,
		                   nivel=1, es_total=True))
		totales[seccion] = (suma_actual, suma_anterior)

	# Estas dos van en líneas propias del modelo, fuera de los totales.
	for rubro in ("Ganancia (pérdida) por diferencia cambiaria",
	              "Participación en resultado de asociadas"):
		filas.append(_fila(rubro, flt(actual.get(rubro)),
		                   flt(anterior.get(rubro)) if comparativo else None))

	extras_a = sum(flt(actual.get(r)) for r in
	               ("Ganancia (pérdida) por diferencia cambiaria",
	                "Participación en resultado de asociadas"))
	extras_b = sum(flt(anterior.get(r)) for r in
	               ("Ganancia (pérdida) por diferencia cambiaria",
	                "Participación en resultado de asociadas"))

	resultado_a = totales[mapeo.INGRESOS][0] - totales[mapeo.GASTOS][0] + extras_a
	resultado_b = totales[mapeo.INGRESOS][1] - totales[mapeo.GASTOS][1] + extras_b

	filas.append(_fila("Resultado del período (ahorro/desahorro)", resultado_a,
	                   resultado_b if comparativo else None, es_total=True))

	filas.append(_fila("Atribuible a:", nivel=1))
	filas.append(_fila("Propietarios de la entidad controladora", resultado_a,
	                   resultado_b if comparativo else None, nivel=2))
	filas.append(_fila("Intereses minoritarios", 0.0, 0.0 if comparativo else None, nivel=2))

	return filas, sin_mapear


def resultado_del_periodo(company, hasta, desde=None):
	"""Ahorro/desahorro acumulado del ejercicio al que pertenece `hasta`.

	Lo consume el Estado de Situación Financiera, donde el resultado todavía no
	capitalizado es un rubro propio del patrimonio.
	"""
	if not desde:
		desde = getdate(hasta).replace(month=1, day=1)

	saldos = saldos_por_cuenta(company, hasta, desde=desde)
	ingresos = gastos = 0.0

	for codigo, monto in saldos.items():
		if not codigo:
			continue
		if codigo.startswith("4"):
			ingresos += flt(monto)
		elif codigo.startswith("5"):
			gastos += flt(monto)

	return ingresos - gastos


# --------------------------------------------------------------------------- #
# 5.3 Estado de Cambios en Activo Neto/Patrimonio
# --------------------------------------------------------------------------- #

COLUMNAS_PATRIMONIO = [
	("capital_aportado", "Capital Aportado", ("3.1.01",)),
	("politicas_contables", "Cambios en Políticas Contables", ("3.1.03.01",)),
	("revaluacion", "Revaluación", ("3.1.03",)),
	("resultados_acumulados", "Resultados Acumulados", ("3.1.04",)),
]


def cambios_patrimonio(company, fiscal_year):
	"""Matriz de movimientos del patrimonio: componentes en columnas, eventos en filas.

	Se construye con dos ciclos (ejercicio anterior y actual) como exige el modelo:
	saldo inicial, movimientos, saldo final.
	"""
	anio = int(frappe.db.get_value("Fiscal Year", fiscal_year, "year_start_date").year)

	def saldo_componente(prefijos, hasta):
		saldos = saldos_por_cuenta(company, hasta)
		total = 0.0
		for codigo, monto in saldos.items():
			if codigo and any(codigo.startswith(p) for p in prefijos):
				total += flt(monto)
		return total

	filas = []
	for desplazamiento in (-1, 0):
		cierre_previo = f"{anio + desplazamiento - 1}-12-31"
		cierre = f"{anio + desplazamiento}-12-31"

		fila_inicial = {"concepto": f"Saldo al 31 de diciembre de {anio + desplazamiento - 1}",
		                "es_total": 1}
		total_inicial = 0.0
		for clave, _etiqueta, prefijos in COLUMNAS_PATRIMONIO:
			valor = saldo_componente(prefijos, cierre_previo)
			fila_inicial[clave] = valor
			total_inicial += valor
		fila_inicial["total"] = total_inicial
		filas.append(fila_inicial)

		# Movimientos del período por componente.
		for concepto, prefijos in (
			("Cambio en políticas contables", ("3.1.03.01",)),
			("Revaluación de Propiedad, planta y equipo", ("3.1.03",)),
			("Ajuste al patrimonio", ("3.1.02",)),
		):
			fila = {"concepto": concepto, "es_total": 0}
			total = 0.0
			for clave, _etiqueta, prefijos_col in COLUMNAS_PATRIMONIO:
				delta = saldo_componente(prefijos_col, cierre) - saldo_componente(
					prefijos_col, cierre_previo
				)
				valor = delta if prefijos_col == prefijos else 0.0
				fila[clave] = valor
				total += valor
			fila["total"] = total
			filas.append(fila)

		resultado = resultado_del_periodo(company, cierre, f"{anio + desplazamiento}-01-01")
		fila_resultado = {"concepto": "Resultado del período", "es_total": 0, "total": resultado}
		for clave, _etiqueta, _p in COLUMNAS_PATRIMONIO:
			fila_resultado[clave] = resultado if clave == "resultados_acumulados" else 0.0
		filas.append(fila_resultado)

	cierre_final = f"{anio}-12-31"
	fila_final = {"concepto": f"Saldo al 31 de diciembre de {anio}", "es_total": 1}
	total_final = 0.0
	for clave, _etiqueta, prefijos in COLUMNAS_PATRIMONIO:
		valor = saldo_componente(prefijos, cierre_final)
		fila_final[clave] = valor
		total_final += valor
	fila_final["total"] = total_final
	filas.append(fila_final)

	return filas


# --------------------------------------------------------------------------- #
# 5.5 Comparación de importes presupuestados y realizados
# --------------------------------------------------------------------------- #


def comparacion_presupuesto(company, fiscal_year):
	"""Presupuesto reformado vs. ejecutado sobre base de efectivo, por objeto del gasto.

	El "ejecutado" es `monto_pagado` del subledger presupuestario, no el devengado: el
	modelo de DIGECOG es explícitamente de base de efectivo.
	"""
	lineas = frappe.db.sql(
		"""
		select a.account_number as codigo,
		       sum(lp.monto_modificado) as reformado,
		       sum(lp.monto_pagado) as ejecutado
		from `tabLinea Presupuestaria` lp
		join `tabAccount` a on a.name = lp.account
		where lp.company = %s and lp.fiscal_year = %s
		group by a.account_number
		""",
		(company, fiscal_year),
		as_dict=True,
	)

	por_objeto = {}
	for linea in lineas:
		objeto, _s = mapeo.resolver(linea.codigo, mapeo.OBJETO_PRESUPUESTARIO)
		if not objeto:
			continue
		acumulado = por_objeto.setdefault(objeto, {"reformado": 0.0, "ejecutado": 0.0})
		acumulado["reformado"] += flt(linea.reformado)
		acumulado["ejecutado"] += flt(linea.ejecutado)

	filas = []
	totales = {}

	for encabezado, objetos in mapeo.ORDEN_OBJETO_PRESUPUESTARIO:
		suma = {"reformado": 0.0, "ejecutado": 0.0}
		detalle = []

		for objeto in objetos:
			valores = por_objeto.get(objeto, {"reformado": 0.0, "ejecutado": 0.0})
			suma["reformado"] += valores["reformado"]
			suma["ejecutado"] += valores["ejecutado"]
			detalle.append(_fila_presupuesto(objeto, valores, nivel=1))

		filas.append(_fila_presupuesto(encabezado, suma, nivel=0, es_total=True))
		filas.extend(detalle)
		totales[encabezado] = suma

	ingresos = totales["1     Ingresos totales"]
	gastos = totales["2     Gastos totales"]
	filas.append(
		_fila_presupuesto(
			"      Resultado financiero (1-2)",
			{
				"reformado": ingresos["reformado"] - gastos["reformado"],
				"ejecutado": ingresos["ejecutado"] - gastos["ejecutado"],
			},
			es_total=True,
		)
	)

	return filas


def _fila_presupuesto(concepto, valores, nivel=0, es_total=False):
	reformado, ejecutado = flt(valores["reformado"]), flt(valores["ejecutado"])
	return {
		"concepto": concepto,
		"presupuesto_reformado": reformado,
		"presupuesto_ejecutado": ejecutado,
		"porcentaje_ejecucion": (ejecutado / reformado * 100) if reformado else 0.0,
		"variacion": reformado - ejecutado,
		"indent": nivel,
		"es_total": 1 if es_total else 0,
	}


# --------------------------------------------------------------------------- #
# 5.4 Estado de Flujo de Efectivo — método directo
# --------------------------------------------------------------------------- #


def _movimientos_de_efectivo(company, desde, hasta):
	"""Asientos completos de los comprobantes que tocaron efectivo en el período."""
	return frappe.db.sql(
		"""
		select gl.voucher_no, a.account_number as codigo,
		       gl.debit as debito, gl.credit as credito
		from `tabGL Entry` gl
		join `tabAccount` a on a.name = gl.account
		where gl.company = %(company)s
		  and gl.is_cancelled = 0
		  and gl.posting_date between %(desde)s and %(hasta)s
		  and gl.voucher_no in (
			select gl2.voucher_no
			from `tabGL Entry` gl2
			join `tabAccount` a2 on a2.name = gl2.account
			where gl2.company = %(company)s
			  and gl2.is_cancelled = 0
			  and gl2.posting_date between %(desde)s and %(hasta)s
			  and a2.account_number like %(efectivo)s
		  )
		""",
		{
			"company": company,
			"desde": getdate(desde),
			"hasta": getdate(hasta),
			"efectivo": mapeo.PREFIJO_EFECTIVO + "%",
		},
		as_dict=True,
	)


def _es_efectivo(codigo):
	return bool(codigo) and codigo.startswith(mapeo.PREFIJO_EFECTIVO)


def flujo_efectivo(company, desde, hasta):
	"""Estado de Flujo de Efectivo por método directo.

	DIGECOG no acepta el método indirecto, así que no se deriva del Estado de
	Rendimiento Financiero: se clasifica cada movimiento de las cuentas de efectivo
	según la naturaleza de su contrapartida en el mismo comprobante.

	Cuando un comprobante tiene varias contrapartidas, el movimiento de caja se
	reparte entre ellas a prorrata de sus montos — es lo más fiel que se puede hacer
	sin que el usuario clasifique cada línea a mano.
	"""
	por_voucher = {}
	for asiento in _movimientos_de_efectivo(company, desde, hasta):
		por_voucher.setdefault(asiento.voucher_no, []).append(asiento)

	lineas = {}
	sin_clasificar = []

	for asientos in por_voucher.values():
		efectivo = sum(
			flt(a.debito) - flt(a.credito) for a in asientos if _es_efectivo(a.codigo)
		)
		if not efectivo:
			continue

		contrapartidas = [
			(a.codigo, abs(flt(a.debito) - flt(a.credito)))
			for a in asientos
			if not _es_efectivo(a.codigo)
		]
		total = sum(monto for _c, monto in contrapartidas)
		if not total:
			continue

		for codigo, monto in contrapartidas:
			porcion = efectivo * (monto / total)
			if not porcion:
				continue

			# FLUJO_EFECTIVO no se resuelve con mapeo.resolver(): sus filas traen
			# cuatro columnas porque la línea depende de si el efectivo entra o sale.
			fila = _fila_flujo(codigo)
			if not fila:
				# Nunca se descarta un movimiento: perderlo descuadraría el estado
				# contra la variación real del efectivo. Va a "Otros" de operación y
				# se reporta aparte para poder afinar el mapeo.
				sin_clasificar.append((codigo, porcion))
				fila = (codigo, mapeo.OPERACION, "Otros cobros", "Otros pagos")

			_prefijo, seccion, linea_cobro, linea_pago = fila
			clave = (seccion, linea_cobro if porcion > 0 else linea_pago)
			lineas[clave] = lineas.get(clave, 0.0) + abs(porcion)

	return _armar_flujo(company, desde, hasta, lineas), sin_clasificar


_INDICE_FLUJO = None


def _fila_flujo(codigo):
	"""Fila completa de FLUJO_EFECTIVO por prefijo más largo."""
	global _INDICE_FLUJO
	if _INDICE_FLUJO is None:
		_INDICE_FLUJO = {fila[0]: fila for fila in mapeo.FLUJO_EFECTIVO}

	partes = (codigo or "").split(".")
	for largo in range(len(partes), 0, -1):
		prefijo = ".".join(partes[:largo])
		if prefijo in _INDICE_FLUJO:
			return _INDICE_FLUJO[prefijo]
	return None


def _saldo_efectivo(company, hasta):
	saldos = saldos_por_cuenta(company, hasta)
	return sum(flt(m) for c, m in saldos.items() if _es_efectivo(c))


def _armar_flujo(company, desde, hasta, lineas):
	filas = []
	neto_total = 0.0

	for seccion, orden, etiqueta_neto in mapeo.ORDEN_FLUJO_EFECTIVO:
		filas.append(_fila(seccion, nivel=0))
		neto = 0.0

		for linea in orden:
			monto = flt(lineas.get((seccion, linea)))
			# Los pagos restan del neto y se muestran en negativo, como el modelo.
			if linea in mapeo.LINEAS_DE_PAGO:
				monto = -monto
			neto += monto
			filas.append(_fila(linea, monto, nivel=1))

		filas.append(_fila(etiqueta_neto, neto, nivel=0, es_total=True))
		neto_total += neto

	inicial = _saldo_efectivo(company, add_days(getdate(desde), -1))
	final = _saldo_efectivo(company, hasta)

	filas.append(_fila("Incremento/(Disminución) neta en el efectivo y equivalentes al efectivo",
	                   neto_total, es_total=True))
	filas.append(_fila("Efectivo y equivalentes al efectivo al principio del periodo", inicial))
	filas.append(_fila("Efectivo y equivalentes al efectivo al final del periodo", final,
	                   es_total=True))

	return filas


def cuadra_flujo_efectivo(filas):
	"""El neto del período tiene que explicar la variación real del efectivo.

	Es la prueba de integridad del estado: inicial + variación == final. Si no da, la
	clasificación se comió o duplicó algún movimiento.
	"""
	def valor(concepto):
		for fila in filas:
			if fila["concepto"] == concepto:
				return flt(fila["monto_actual"])
		return 0.0

	inicial = valor("Efectivo y equivalentes al efectivo al principio del periodo")
	final = valor("Efectivo y equivalentes al efectivo al final del periodo")
	variacion = valor("Incremento/(Disminución) neta en el efectivo y equivalentes al efectivo")
	return abs((inicial + variacion) - final) < 0.01
