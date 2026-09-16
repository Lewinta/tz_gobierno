# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Mapeo cuenta DIGECOG → rubro de cada Estado Financiero oficial.

Los modelos de los 5 estados que publica DIGECOG tienen rubros con nombres propios
que no coinciden uno a uno con los grupos del plan de cuentas. Este módulo concentra
esa correspondencia para poder ajustarla sin tocar el código de los reportes — que es
justo lo que va a hacer falta cuando el CES revise los primeros estados emitidos.

RESOLUCIÓN POR PREFIJO MÁS LARGO
--------------------------------
Una cuenta se asigna al rubro cuyo prefijo de código sea el más largo que la contenga.
Así `1.1.04.07` (Pagos anticipados) va a su propio rubro aunque `1.1.04` (Cuentas por
cobrar) también la contenga. Permite empezar con mapeos gruesos de nivel 3 e ir
afinando a nivel 4 o 5 sin reescribir nada.
"""

# --------------------------------------------------------------------------- #
# 5.1 Estado de Situación Financiera
# --------------------------------------------------------------------------- #

ACTIVO_CORRIENTE = "Activos corrientes"
ACTIVO_NO_CORRIENTE = "Activos no corrientes"
PASIVO_CORRIENTE = "Pasivos corrientes"
PASIVO_NO_CORRIENTE = "Pasivos no corrientes"
PATRIMONIO = "Activos Netos/Patrimonio"

# (prefijo, rubro, sección). El orden no importa: gana el prefijo más largo.
SITUACION_FINANCIERA = [
	# Activos corrientes
	("1.1.01", "Efectivo y equivalente de efectivo", ACTIVO_CORRIENTE),
	("1.1.02", "Inversiones a corto plazo", ACTIVO_CORRIENTE),
	("1.1.03", "Porción corriente de documentos por cobrar", ACTIVO_CORRIENTE),
	("1.1.04", "Cuenta por cobrar a corto plazo", ACTIVO_CORRIENTE),
	("1.1.04.07", "Pagos anticipados", ACTIVO_CORRIENTE),
	("1.1.05", "Inventarios", ACTIVO_CORRIENTE),
	("1.1.09", "Otros activos corrientes", ACTIVO_CORRIENTE),
	# Activos no corrientes
	("1.2.01", "Cuentas por cobrar a largo plazo", ACTIVO_NO_CORRIENTE),
	("1.2.02", "Documentos por cobrar", ACTIVO_NO_CORRIENTE),
	("1.2.03", "Inversiones a largo plazo", ACTIVO_NO_CORRIENTE),
	("1.2.04", "Inversiones a largo plazo", ACTIVO_NO_CORRIENTE),
	("1.2.05", "Propiedad, planta y equipo neto", ACTIVO_NO_CORRIENTE),
	("1.2.06", "Propiedad, planta y equipo neto", ACTIVO_NO_CORRIENTE),
	("1.2.07", "Propiedad, planta y equipo neto", ACTIVO_NO_CORRIENTE),
	("1.2.08", "Propiedad, planta y equipo neto", ACTIVO_NO_CORRIENTE),
	("1.2.10", "Propiedad, planta y equipo neto", ACTIVO_NO_CORRIENTE),
	("1.2.09", "Activos intangibles", ACTIVO_NO_CORRIENTE),
	("1.2.11", "Otros activos no financieros", ACTIVO_NO_CORRIENTE),
	("1.2.11.06", "Otros activos financieros", ACTIVO_NO_CORRIENTE),
	# Pasivos corrientes
	("2.1.01", "Cuentas por pagar a corto plazo", PASIVO_CORRIENTE),
	("2.1.02", "Préstamos a corto plazo", PASIVO_CORRIENTE),
	("2.1.02.01", "Sobregiro bancario", PASIVO_CORRIENTE),
	("2.1.03", "Parte corriente de préstamos a largo plazo", PASIVO_CORRIENTE),
	("2.1.04", "Retenciones y acumulaciones por pagar", PASIVO_CORRIENTE),
	("2.1.05", "Provisiones a corto plazo", PASIVO_CORRIENTE),
	("2.1.06", "Beneficios a empleados a corto plazo", PASIVO_CORRIENTE),
	("2.1.07", "Pensiones", PASIVO_CORRIENTE),
	("2.1.09", "Otros pasivos corrientes", PASIVO_CORRIENTE),
	# Pasivos no corrientes
	("2.2.01", "Cuentas por pagar a largo plazo", PASIVO_NO_CORRIENTE),
	("2.2.02", "Préstamos a largo plazo", PASIVO_NO_CORRIENTE),
	("2.2.03", "Instrumentos de deuda", PASIVO_NO_CORRIENTE),
	("2.2.04", "Provisiones a largo plazo", PASIVO_NO_CORRIENTE),
	("2.2.05", "Beneficios a empleados a largo plazo", PASIVO_NO_CORRIENTE),
	("2.2.09", "Otros pasivos no corrientes", PASIVO_NO_CORRIENTE),
	# Patrimonio
	("3.1.01", "Capital", PATRIMONIO),
	("3.1.02", "Reservas", PATRIMONIO),
	("3.1.03", "Reservas", PATRIMONIO),
	("3.1.04", "Resultado acumulado", PATRIMONIO),
	("3.2", "Intereses minoritarios", PATRIMONIO),
]

# Orden exacto de los rubros en el modelo oficial. Un rubro sin saldo igual se
# imprime en cero: el modelo de DIGECOG es de formato fijo.
ORDEN_SITUACION_FINANCIERA = [
	(ACTIVO_CORRIENTE, [
		"Efectivo y equivalente de efectivo",
		"Inversiones a corto plazo",
		"Porción corriente de documentos por cobrar",
		"Cuenta por cobrar a corto plazo",
		"Inventarios",
		"Pagos anticipados",
		"Otros activos corrientes",
	]),
	(ACTIVO_NO_CORRIENTE, [
		"Cuentas por cobrar a largo plazo",
		"Documentos por cobrar",
		"Inversiones a largo plazo",
		"Otros activos financieros",
		"Propiedad, planta y equipo neto",
		"Activos intangibles",
		"Otros activos no financieros",
	]),
	(PASIVO_CORRIENTE, [
		"Sobregiro bancario",
		"Cuentas por pagar a corto plazo",
		"Préstamos a corto plazo",
		"Parte corriente de préstamos a largo plazo",
		"Retenciones y acumulaciones por pagar",
		"Provisiones a corto plazo",
		"Beneficios a empleados a corto plazo",
		"Pensiones",
		"Otros pasivos corrientes",
	]),
	(PASIVO_NO_CORRIENTE, [
		"Cuentas por pagar a largo plazo",
		"Préstamos a largo plazo",
		"Instrumentos de deuda",
		"Provisiones a largo plazo",
		"Beneficios a empleados a largo plazo",
		"Otros pasivos no corrientes",
	]),
	(PATRIMONIO, [
		"Capital",
		"Reservas",
		"Resultados positivos (ahorro)/negativo (desahorro)",
		"Resultado acumulado",
		"Intereses minoritarios",
	]),
]

# Se calcula desde el Estado de Rendimiento Financiero, no desde una cuenta.
RUBRO_RESULTADO_DEL_PERIODO = "Resultados positivos (ahorro)/negativo (desahorro)"


# --------------------------------------------------------------------------- #
# 5.2 Estado de Rendimiento Financiero
# --------------------------------------------------------------------------- #

INGRESOS = "Ingresos"
GASTOS = "Gastos"
RESULTADOS_APARTE = "Resultados presentados por separado"

RENDIMIENTO_FINANCIERO = [
	("4.1", "Impuestos", INGRESOS),
	("4.2", "Transferencias y donaciones", INGRESOS),
	("4.3", "Ingresos por transacciones con contraprestación", INGRESOS),
	("4.4", "Recargos, multas y otros ingresos", INGRESOS),
	("4.9", "Recargos, multas y otros ingresos", INGRESOS),
	# Estas dos se presentan en líneas propias del modelo, fuera de los totales
	# de ingresos y gastos, así que se sacan de sus grupos por prefijo más largo.
	("4.4.01", "Participación en resultado de asociadas", RESULTADOS_APARTE),
	("5.5.01", "Participación en resultado de asociadas", RESULTADOS_APARTE),
	("4.4.02", "Ganancia (pérdida) por diferencia cambiaria", RESULTADOS_APARTE),
	("5.5.02", "Ganancia (pérdida) por diferencia cambiaria", RESULTADOS_APARTE),
	("5.1.01", "Sueldos, salarios y beneficios a empleados", GASTOS),
	("5.1.02", "Otros gastos", GASTOS),
	("5.1.03", "Suministros y material para consumo", GASTOS),
	("5.1.04", "Gasto de depreciación y amortización", GASTOS),
	("5.1.05", "Deterioro del valor de propiedad, planta y equipo", GASTOS),
	("5.1.06", "Deterioro del valor de propiedad, planta y equipo", GASTOS),
	("5.1.07", "Otros gastos", GASTOS),
	("5.2", "Subvenciones y otros pagos por transferencias", GASTOS),
	("5.3", "Otros gastos", GASTOS),
	("5.4", "Gastos financieros", GASTOS),
	("5.5", "Otros gastos", GASTOS),
]

ORDEN_RENDIMIENTO_FINANCIERO = [
	(INGRESOS, [
		"Impuestos",
		"Ingresos por transacciones con contraprestación",
		"Transferencias y donaciones",
		"Recargos, multas y otros ingresos",
	]),
	(GASTOS, [
		"Sueldos, salarios y beneficios a empleados",
		"Subvenciones y otros pagos por transferencias",
		"Suministros y material para consumo",
		"Gasto de depreciación y amortización",
		"Deterioro del valor de propiedad, planta y equipo",
		"Otros gastos",
		"Gastos financieros",
	]),
	(RESULTADOS_APARTE, [
		"Ganancia (pérdida) por diferencia cambiaria",
		"Participación en resultado de asociadas",
	]),
]


# --------------------------------------------------------------------------- #
# 5.5 Comparación presupuesto vs. ejecución — objeto del gasto
# --------------------------------------------------------------------------- #

# TODO: ajustar con el Manual de Clasificadores Presupuestario para el Sector
# Público cuando Lewin lo consiga. Mientras tanto se aproxima por los grupos de
# nivel 2-3 del plan DIGECOG, que siguen la misma lógica económica.
OBJETO_PRESUPUESTARIO = [
	("4.1", "1.1   Impuestos"),
	("4.2.01", "1.2   Contribuciones Sociales"),
	("4.2.02", "1.3   Donaciones"),
	("4.2.03", "1.4   Transferencias"),
	("4.2.04", "1.4   Transferencias"),
	("4.2.09", "1.6   Otros ingresos"),
	("4.3", "1.5   Ingresos por contraprestación"),
	("4.4", "1.6   Otros ingresos"),
	("4.9", "1.9   Ingresos a especificar"),
	("5.1.01", "2.1   Remuneraciones y contribuciones"),
	("5.1.02", "2.2   Contratación de servicios"),
	("5.1.03", "2.3   Materiales y suministros"),
	("5.2.01", "2.4   Transferencias corrientes"),
	("5.2.02", "2.5   Transferencias de capital"),
	("5.1.04", "2.6   Bienes muebles, inmuebles e intangibles"),
	("5.1.05", "2.6   Bienes muebles, inmuebles e intangibles"),
	("5.1.06", "2.6   Bienes muebles, inmuebles e intangibles"),
	("5.4", "2.9   Gastos financieros"),
	("5.1.07", "2.9   Gastos financieros"),
	("5.3", "2.2   Contratación de servicios"),
	("5.5", "2.9   Gastos financieros"),
]

ORDEN_OBJETO_PRESUPUESTARIO = [
	("1     Ingresos totales", [
		"1.1   Impuestos",
		"1.2   Contribuciones Sociales",
		"1.3   Donaciones",
		"1.4   Transferencias",
		"1.5   Ingresos por contraprestación",
		"1.6   Otros ingresos",
		"1.7   Venta de activos no financieros",
		"1.8   Activos financieros con fines de política",
		"1.9   Ingresos a especificar",
	]),
	("2     Gastos totales", [
		"2.1   Remuneraciones y contribuciones",
		"2.2   Contratación de servicios",
		"2.3   Materiales y suministros",
		"2.4   Transferencias corrientes",
		"2.5   Transferencias de capital",
		"2.6   Bienes muebles, inmuebles e intangibles",
		"2.7   Obras",
		"2.8   Adquisición de activos financieros con fines de política",
		"2.9   Gastos financieros",
	]),
]


# --------------------------------------------------------------------------- #
# Resolución
# --------------------------------------------------------------------------- #


def _indice(tabla):
	"""{prefijo: (rubro, seccion)} — la tabla puede traer 2 o 3 elementos por fila."""
	indice = {}
	for fila in tabla:
		prefijo, rubro = fila[0], fila[1]
		seccion = fila[2] if len(fila) > 2 else None
		indice[prefijo] = (rubro, seccion)
	return indice


_INDICES = {}


def resolver(codigo, tabla):
	"""Rubro y sección del código, por el prefijo más largo que lo contenga.

	Devuelve (None, None) si ninguna entrada aplica — el llamador decide si eso es
	un hueco del mapeo que hay que reportar o una cuenta que no va en ese estado.
	"""
	clave = id(tabla)
	if clave not in _INDICES:
		_INDICES[clave] = _indice(tabla)
	indice = _INDICES[clave]

	partes = (codigo or "").split(".")
	for largo in range(len(partes), 0, -1):
		prefijo = ".".join(partes[:largo])
		if prefijo in indice:
			return indice[prefijo]

	return None, None


# --------------------------------------------------------------------------- #
# 5.4 Estado de Flujo de Efectivo — método directo
# --------------------------------------------------------------------------- #

# DIGECOG no acepta el método indirecto, así que el estado se arma clasificando cada
# movimiento de las cuentas de efectivo (clase 1.1.01) por la naturaleza de su
# contrapartida. Un mismo prefijo de contrapartida produce una línea distinta según
# el flujo entre o salga, de ahí que cada entrada traiga ambas.
#
# TODO: validar la clasificación contra el Manual de Estados Financieros de DIGECOG
# antes de la demo. La lógica económica es la estándar del sector público, pero el
# manual puede asignar algún concepto a otra línea.

OPERACION = "Flujo de efectivo procedentes de actividades operativas"
INVERSION = "Flujos de efectivo de las actividades de inversión"
FINANCIACION = "Flujos de efectivo de las actividades de financiación"

# (prefijo de la contrapartida, sección, línea si ENTRA efectivo, línea si SALE)
FLUJO_EFECTIVO = [
	# --- Operación ---
	("4.1", OPERACION, "Cobros impuestos", "Otros pagos"),
	("4.2.01", OPERACION, "Contribuciones de la seguridad social", "Otros pagos"),
	("4.3.01", OPERACION, "Cobros por venta de bienes y servicios y arrendamientos", "Otros pagos"),
	("4.3.02", OPERACION, "Cobros por venta de bienes y servicios y arrendamientos", "Otros pagos"),
	("4.3.03", OPERACION, "Cobros por venta de bienes y servicios y arrendamientos", "Otros pagos"),
	("4.2.02", OPERACION, "Cobros de subvenciones, transferencias, y otras asignaciones", "Otros pagos"),
	("4.2.03", OPERACION, "Cobros de subvenciones, transferencias, y otras asignaciones", "Otros pagos"),
	("4.2.04", OPERACION, "Cobros de subvenciones, transferencias, y otras asignaciones", "Otros pagos"),
	("4.4.03", OPERACION, "Cobros por contratos mantenidos para negocios o intercambio",
	 "Pagos por contratos mantenidos para negocios o intercambio"),
	("5.5.03", OPERACION, "Cobros por contratos mantenidos para negocios o intercambio",
	 "Pagos por contratos mantenidos para negocios o intercambio"),
	("4.3.06", OPERACION, "Cobros de intereses financieros", "Pagos de intereses"),
	("4.2.09", OPERACION, "Otros cobros", "Otros pagos"),
	("4.3.04", OPERACION, "Otros cobros", "Otros pagos"),
	("4.3.05", OPERACION, "Otros cobros", "Otros pagos"),
	("4.3.09", OPERACION, "Otros cobros", "Otros pagos"),
	("4.4", OPERACION, "Otros cobros", "Otros pagos"),
	("4.9", OPERACION, "Otros cobros", "Otros pagos"),
	("5.2", OPERACION, "Otros cobros",
	 "Pagos a otras entidades para financiar sus operaciones (Transferencias)"),
	("5.1.01", OPERACION, "Otros cobros", "Pagos a los trabajadores o en beneficio de ellos"),
	("2.1.06", OPERACION, "Otros cobros", "Pagos a los trabajadores o en beneficio de ellos"),
	("2.1.04", OPERACION, "Otros cobros", "Pagos por contribuciones a la seguridad social"),
	("2.1.07", OPERACION, "Otros cobros", "Pagos de pensiones y jubilaciones"),
	("2.1.01", OPERACION, "Otros cobros", "Pagos a proveedores"),
	("5.1.02", OPERACION, "Otros cobros", "Pagos a proveedores"),
	("5.1.03", OPERACION, "Otros cobros", "Pagos a proveedores"),
	("5.3", OPERACION, "Otros cobros", "Pagos a proveedores"),
	("1.1.05", OPERACION, "Otros cobros", "Pagos a proveedores"),
	("5.4.01", OPERACION, "Cobros de intereses financieros", "Pagos de intereses"),
	("5.1.04", OPERACION, "Otros cobros", "Otros pagos"),
	("5.1.05", OPERACION, "Otros cobros", "Otros pagos"),
	("5.1.06", OPERACION, "Otros cobros", "Otros pagos"),
	("5.1.07", OPERACION, "Otros cobros", "Otros pagos"),
	("5.4", OPERACION, "Otros cobros", "Otros pagos"),
	("5.5", OPERACION, "Otros cobros", "Otros pagos"),
	("1.1.04", OPERACION, "Otros cobros", "Otros pagos"),
	("1.1.09", OPERACION, "Otros cobros", "Otros pagos"),
	("2.1.05", OPERACION, "Otros cobros", "Otros pagos"),
	("2.1.09", OPERACION, "Otros cobros", "Otros pagos"),
	("1.1.09", OPERACION, "Otros cobros", "Otros pagos"),
	# --- Inversión ---
	("1.2.05", INVERSION, "Cobros por venta de propiedad, planta y equipo",
	 "Pagos por adquisición de propiedad, planta y equipo"),
	("1.2.06", INVERSION, "Cobros por venta de propiedad, planta y equipo",
	 "Pagos por adquisición de propiedad, planta y equipo"),
	("1.2.07", INVERSION, "Cobros por venta de propiedad, planta y equipo",
	 "Pagos por adquisición de propiedad, planta y equipo"),
	("1.2.08", INVERSION, "Cobros por venta de propiedad, planta y equipo",
	 "Pagos por adquisición de propiedad, planta y equipo"),
	("1.2.10", INVERSION, "Cobros por venta de propiedad, planta y equipo",
	 "Pagos por adquisición de propiedad, planta y equipo"),
	("1.2.09", INVERSION, "Cobros por venta de intangibles y otros activos de largo plazo",
	 "Pagos por adquisición de intangibles y otros activos de largo plazo"),
	("1.2.11", INVERSION, "Cobros por venta de intangibles y otros activos de largo plazo",
	 "Pagos por adquisición de intangibles y otros activos de largo plazo"),
	("1.2.03", INVERSION,
	 "Cobros por títulos patrimoniales o de deuda y participación en asociaciones",
	 "Pagos por adquisición de títulos patrimoniales o de deuda y participación en asociaciones"),
	("1.2.04", INVERSION,
	 "Cobros por títulos patrimoniales o de deuda y participación en asociaciones",
	 "Pagos por adquisición de títulos patrimoniales o de deuda y participación en asociaciones"),
	("1.1.02", INVERSION,
	 "Cobros por títulos patrimoniales o de deuda y participación en asociaciones",
	 "Pagos por adquisición de títulos patrimoniales o de deuda y participación en asociaciones"),
	("1.1.04.04", INVERSION, "Cobros por reembolsos de préstamos o anticipos hechos a terceros",
	 "Pagos por otorgamiento de préstamos o anticipos hechos a terceros"),
	("1.1.03", INVERSION, "Cobros por reembolsos de préstamos o anticipos hechos a terceros",
	 "Pagos por otorgamiento de préstamos o anticipos hechos a terceros"),
	("1.2.01", INVERSION, "Cobros por reembolsos de préstamos o anticipos hechos a terceros",
	 "Pagos por otorgamiento de préstamos o anticipos hechos a terceros"),
	("1.2.02", INVERSION, "Cobros por reembolsos de préstamos o anticipos hechos a terceros",
	 "Pagos por otorgamiento de préstamos o anticipos hechos a terceros"),
	# --- Financiación ---
	("2.2.03", FINANCIACION, "Cobro por emisión de títulos de deudas, bonos",
	 "Pago reembolso en efectivo de los montos recibidos en emisión de títulos de deudas, bonos"),
	("2.1.02", FINANCIACION, "Cobro por préstamos, pagarés, hipotecas",
	 "Pago reembolso en efectivo de los montos recibidos en préstamos, pagarés, hipotecas"),
	("2.1.03", FINANCIACION, "Cobro por préstamos, pagarés, hipotecas",
	 "Pago reembolso en efectivo de los montos recibidos en préstamos, pagarés, hipotecas"),
	("2.2.02", FINANCIACION, "Cobro por préstamos, pagarés, hipotecas",
	 "Pago reembolso en efectivo de los montos recibidos en préstamos, pagarés, hipotecas"),
	("2.2.01", FINANCIACION, "Cobro por préstamos, pagarés, hipotecas",
	 "Pago reembolso en efectivo de los montos recibidos en préstamos, pagarés, hipotecas"),
	("2.2.04", FINANCIACION, "Otros cobros", "Otros pagos"),
	("2.2.05", FINANCIACION, "Otros cobros", "Otros pagos"),
	("2.2.09", FINANCIACION, "Otros cobros", "Otros pagos"),
	("3.1.01", FINANCIACION, "Cobro por aporte de accionista",
	 "Pago reembolso de efectivo recibió por aporte de accionista"),
	("3.1.02", FINANCIACION, "Otros cobros", "Pago por distribución/dividendos al gobierno"),
	("3.1.03", FINANCIACION, "Otros cobros", "Pago por distribución/dividendos al gobierno"),
	("3.1.04", FINANCIACION, "Otros cobros", "Pago por distribución/dividendos al gobierno"),
	("3.2", FINANCIACION, "Otros cobros", "Pago por distribución/dividendos al gobierno"),
	("1.2.11.02", FINANCIACION,
	 "Cobro de los arrendatarios por contratos de arrendamientos financieros",
	 "Pago de los arrendatarios por contratos de arrendamientos financieros"),
]

ORDEN_FLUJO_EFECTIVO = [
	(OPERACION, [
		"Cobros impuestos",
		"Contribuciones de la seguridad social",
		"Cobros por venta de bienes y servicios y arrendamientos",
		"Cobros de subvenciones, transferencias, y otras asignaciones",
		"Cobros de seguros por primas, reclamos y otros",
		"Cobros por contratos mantenidos para negocios o intercambio",
		"Cobros de intereses financieros",
		"Otros cobros",
		"Pagos a otras entidades para financiar sus operaciones (Transferencias)",
		"Pagos a los trabajadores o en beneficio de ellos",
		"Pagos por contribuciones a la seguridad social",
		"Pagos de pensiones y jubilaciones",
		"Pagos a proveedores",
		"Pagos por contratos mantenidos para negocios o intercambio",
		"Pagos de intereses",
		"Otros pagos",
	], "Flujos de efectivo netos de las actividades de operación"),
	(INVERSION, [
		"Cobros por venta de propiedad, planta y equipo",
		"Cobros por venta de intangibles y otros activos de largo plazo",
		"Cobros por títulos patrimoniales o de deuda y participación en asociaciones",
		"Cobros por reembolsos de préstamos o anticipos hechos a terceros",
		"Cobros por conceptos de contratos a futuro, a plazo, opciones o permuta",
		"Otros cobros",
		"Pagos por adquisición de propiedad, planta y equipo",
		"Pagos por adquisición de intangibles y otros activos de largo plazo",
		"Pagos por adquisición de títulos patrimoniales o de deuda y participación en asociaciones",
		"Pagos por otorgamiento de préstamos o anticipos hechos a terceros",
		"Pagos por conceptos de contratos a futuro, a plazo, opciones o permuta",
		"Pagos por costos de construcciones y desarrollos en proceso",
		"Otros pagos",
	], "Flujos de efectivo netos por las actividades de inversión"),
	(FINANCIACION, [
		"Cobro por emisión de títulos de deudas, bonos",
		"Cobro por préstamos, pagarés, hipotecas",
		"Cobro por aporte de accionista",
		"Cobro de los arrendatarios por contratos de arrendamientos financieros",
		"Otros cobros",
		"Pago reembolso en efectivo de los montos recibidos en emisión de títulos de deudas, bonos",
		"Pago reembolso en efectivo de los montos recibidos en préstamos, pagarés, hipotecas",
		"Pago reembolso de efectivo recibió por aporte de accionista",
		"Pago por distribución/dividendos al gobierno",
		"Pago de los arrendatarios por contratos de arrendamientos financieros",
		"Otros pagos",
	], "Flujos de efectivo netos por las actividades de financiación"),
]

# Las líneas que restan en el neto de cada sección.
LINEAS_DE_PAGO = {
	linea for _seccion, lineas, _neto in ORDEN_FLUJO_EFECTIVO
	for linea in lineas if linea.lower().startswith("pago")
}

PREFIJO_EFECTIVO = "1.1.01"
