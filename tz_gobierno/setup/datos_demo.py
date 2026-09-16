# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Datos de demostración para la institución del pliego CES-DAF-CM-2026-0009.

Genera dos ejercicios completos (2025 y 2026) sobre el plan DIGECOG ya importado:
presupuesto, financiamiento, ciclo de compras que ejercita el subledger
compromiso→devengado→pagado, activos con depreciación, nómina, y los módulos
secundarios.

Está aquí y no en un script suelto a propósito: si hay que rearmar el sitio antes de
la demo del 09/10, la data se vuelve a sembrar con un comando en vez de a mano.

Es idempotente en lo que puede serlo (masters, presupuesto, activos) y detecta si ya
sembró las transacciones de un año para no duplicarlas.

    bench --site gob.tzcode.net execute tz_gobierno.setup.datos_demo.ejecutar
"""

import frappe
from frappe.utils import add_days, add_months, flt, getdate, nowdate

COMPANY = "CES - Consejo Económico y Social"
ABBR = "CES"
ANIOS = (2025, 2026)

# --------------------------------------------------------------------------- #
# Cuentas del plan DIGECOG que usa la demo.
# Son códigos reales del plan oficial, no inventados: la demo tiene que verse como
# la contabilidad de una institución pública dominicana de verdad.
# --------------------------------------------------------------------------- #

CUENTAS = {
	"banco": "1.1.01.02.01.01.01",        # BanReservas cuenta única en RD$
	"caja_chica": "1.1.01.01.01.02",      # Efectivo en caja chica en el país
	"proveedores": "2.1.01.01.01.01",     # Proveedores a pagar al sector privado interno c/p
	"tarjeta": "2.1.01.99.01",            # Cuentas varias a pagar c/p
	"retenciones": "2.1.04.01.01",        # Impuestos a pagar c/p
	"nomina_por_pagar": "2.1.06.01.01",   # Remuneraciones a pagar c/p
	"capital": "3.1.01.01.01",            # Capital inicial a valores históricos
	"transferencias_recibidas": "4.2.03.01.02.01",  # Transferencias corrientes de la Adm. Central
	"sueldos": "5.1.01.01.01.01",         # Sueldos fijos
	"telefono": "5.1.02.01.03",           # Teléfono local
	"materiales": "5.1.03.01.01",         # Alimentos y bebidas consumidos
	# Activos: cada familia DIGECOG trae .01 valores de origen y .03 depreciación acumulada.
	"mobiliario_costo": "1.2.06.01.04.99.01",
	"mobiliario_deprec_acum": "1.2.06.01.04.99.03",
	"mobiliario_deprec_gasto": "5.1.04.01.01.05",
}


def cuenta(clave):
	"""Nombre del documento Account a partir de la clave lógica."""
	codigo = CUENTAS[clave]
	nombre = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_number": codigo}, "name"
	)
	if not nombre:
		frappe.throw(f"No existe la cuenta DIGECOG {codigo} ({clave}) en {COMPANY}")
	return nombre


# --------------------------------------------------------------------------- #
# Cimientos
# --------------------------------------------------------------------------- #


def anios_fiscales():
	"""Año fiscal = año calendario, como en todo el sector público dominicano."""
	creados = []
	for anio in ANIOS:
		if frappe.db.exists("Fiscal Year", str(anio)):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": str(anio),
				"year_start_date": f"{anio}-01-01",
				"year_end_date": f"{anio}-12-31",
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		creados.append(str(anio))
	return creados


def preparar_company():
	"""Fija los valores por defecto que ERPNext exige para operar.

	La Company se creó sin plan de cuentas para poder importar el DIGECOG limpio, así
	que ninguno de estos defaults quedó puesto.
	"""
	frappe.db.set_value(
		"Company",
		COMPANY,
		{
			"default_currency": "DOP",
			"country": "Dominican Republic",
			"default_payable_account": cuenta("proveedores"),
			"default_bank_account": cuenta("banco"),
			"default_cash_account": cuenta("caja_chica"),
			"round_off_account": cuenta("telefono"),
			"write_off_account": cuenta("telefono"),
			"exchange_gain_loss_account": cuenta("telefono"),
			"accumulated_depreciation_account": cuenta("mobiliario_deprec_acum"),
			"depreciation_expense_account": cuenta("mobiliario_deprec_gasto"),
			"disposal_account": cuenta("telefono"),
			# hrms lo agrega a Company como Custom Field, con prefijo `default_`.
			"default_payroll_payable_account": cuenta("nomina_por_pagar"),
			# Una institución de servicios no lleva inventario perpetuo; con esto
			# activado, cada factura de compra exigiría cuentas de stock.
			"enable_perpetual_inventory": 0,
		},
	)
	# Marcar las cuentas con su tipo para que ERPNext las reconozca.
	for clave, tipo in (
		("banco", "Bank"),
		("caja_chica", "Cash"),
		("proveedores", "Payable"),
		# ERPNext exige que la cuenta de nómina por pagar sea de tipo Payable.
		("nomina_por_pagar", "Payable"),
		("mobiliario_deprec_acum", "Accumulated Depreciation"),
		("mobiliario_deprec_gasto", "Depreciation"),
		("mobiliario_costo", "Fixed Asset"),
	):
		frappe.db.set_value("Account", cuenta(clave), "account_type", tipo)

	frappe.db.commit()


def centros_costo():
	"""Centros de costo por dirección, que es como presupuesta una institución."""
	raiz = f"{COMPANY} - {ABBR}"
	nombres = [
		"Dirección Administrativa y Financiera",
		"Dirección de Planificación",
		"Consejo Consultivo",
	]
	creados = {}

	for nombre in nombres:
		docname = f"{nombre} - {ABBR}"
		if frappe.db.exists("Cost Center", docname):
			creados[nombre] = docname
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": nombre,
				"parent_cost_center": raiz,
				"company": COMPANY,
				"is_group": 0,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		creados[nombre] = doc.name

	return creados


def _existe_o_crea(doctype, filtros, datos):
	existente = frappe.db.get_value(doctype, filtros, "name")
	if existente:
		return existente
	doc = frappe.get_doc(dict(doctype=doctype, **datos))
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = True
	doc.insert()
	return doc.name


def suplidores():
	"""Suplidores con RNC de dígito verificador válido, que es lo que valida el app."""
	datos = [
		("Suministros de Oficina del Caribe SRL", "130862346"),
		("Servicios Tecnológicos Quisqueya SRL", "131298753"),
		("Mobiliario Corporativo Duarte SRL", "130568741"),
	]
	creados = []
	for nombre, rnc in datos:
		creados.append(
			_existe_o_crea(
				"Supplier",
				{"supplier_name": nombre},
				{
					"supplier_name": nombre,
					"supplier_group": "All Supplier Groups",
					"supplier_type": "Company",
					"tax_id": rnc,
					"rnc_verificado": 1,
				},
			)
		)
	return creados


def articulos():
	"""Artículos de servicio: una institución de este tipo no maneja inventario."""
	datos = [
		("SERV-TELECOM", "Servicio de telecomunicaciones"),
		("SUM-OFICINA", "Suministros de oficina"),
		("MOB-ESCRITORIO", "Mobiliario de oficina"),
	]
	creados = []
	for codigo, nombre in datos:
		creados.append(
			_existe_o_crea(
				"Item",
				{"item_code": codigo},
				{
					"item_code": codigo,
					"item_name": nombre,
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_purchase_item": 1,
				},
			)
		)
	return creados


# --------------------------------------------------------------------------- #
# Presupuesto
# --------------------------------------------------------------------------- #

# (clave de cuenta, centro de costo, monto formulado 2025, monto formulado 2026)
FORMULACION = [
	("sueldos", "Dirección Administrativa y Financiera", 18_000_000, 19_800_000),
	# Todo centro de costo con personal necesita su línea de sueldos: sin ella, la
	# nómina de esa dirección no aparece como ejecución presupuestaria.
	("sueldos", "Dirección de Planificación", 1_400_000, 1_540_000),
	("sueldos", "Consejo Consultivo", 900_000, 990_000),
	("telefono", "Dirección Administrativa y Financiera", 1_200_000, 1_320_000),
	("materiales", "Dirección Administrativa y Financiera", 2_400_000, 2_640_000),
	("telefono", "Dirección de Planificación", 480_000, 528_000),
	("materiales", "Dirección de Planificación", 900_000, 990_000),
	("materiales", "Consejo Consultivo", 600_000, 660_000),
]


def presupuesto(anio):
	"""Formula el presupuesto del ejercicio. Idempotente por la clave compuesta."""
	centros = centros_costo()
	creadas = []

	for clave, centro, monto_2025, monto_2026 in FORMULACION:
		monto = monto_2025 if anio == 2025 else monto_2026
		cuenta_doc = cuenta(clave)
		cc = centros[centro]

		existente = frappe.db.get_value(
			"Linea Presupuestaria",
			{
				"company": COMPANY,
				"fiscal_year": str(anio),
				"account": cuenta_doc,
				"cost_center": cc,
			},
		)
		if existente:
			creadas.append(existente)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Linea Presupuestaria",
				"company": COMPANY,
				"fiscal_year": str(anio),
				"account": cuenta_doc,
				"cost_center": cc,
				"monto_formulado": monto,
				# El modificado arranca igual al formulado; una modificación
				# presupuestaria del ejercicio lo cambia (ver abajo).
				"monto_modificado": monto,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		creadas.append(doc.name)

	return creadas


def modificacion_presupuestaria(anio):
	"""Una reformulación real del ejercicio, para que el reporte 5.5 muestre A≠formulado.

	En 2025 se amplía el presupuesto de materiales de la DAF en RD$300,000, que es el
	tipo de movimiento que el Estado de Comparación tiene que reflejar.
	"""
	centros = centros_costo()
	linea = frappe.db.get_value(
		"Linea Presupuestaria",
		{
			"company": COMPANY,
			"fiscal_year": str(anio),
			"account": cuenta("materiales"),
			"cost_center": centros["Dirección Administrativa y Financiera"],
		},
	)
	if not linea:
		return None

	doc = frappe.get_doc("Linea Presupuestaria", linea)
	if flt(doc.monto_modificado) != flt(doc.monto_formulado):
		return doc.name  # ya modificada

	doc.monto_modificado = flt(doc.monto_formulado) + 300_000
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.name


# --------------------------------------------------------------------------- #
# Financiamiento: la Administración Central transfiere a la institución
# --------------------------------------------------------------------------- #


def _asiento(fecha, concepto, lineas):
	"""Crea y confirma un Journal Entry. `lineas` = [(cuenta, debe, haber, cc)]."""
	filas = []
	for cuenta_doc, debe, haber, cc in lineas:
		fila = {"account": cuenta_doc}
		if debe:
			fila["debit_in_account_currency"] = flt(debe)
		if haber:
			fila["credit_in_account_currency"] = flt(haber)
		if cc:
			fila["cost_center"] = cc
		filas.append(fila)

	doc = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"company": COMPANY,
			"posting_date": fecha,
			"user_remark": concepto,
			"accounts": filas,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
	return doc.name


def financiamiento(anio):
	"""Transferencias corrientes recibidas de la Administración Central, trimestrales.

	Es la fuente de ingresos típica de un consejo consultivo del Estado: no vende
	nada, se financia con transferencias del presupuesto nacional.
	"""
	centros = centros_costo()
	cc = centros["Dirección Administrativa y Financiera"]
	monto = 7_000_000 if anio == 2025 else 7_700_000

	if frappe.db.exists(
		"Journal Entry",
		{"company": COMPANY, "docstatus": 1,
		 "user_remark": ["like", f"Transferencia corriente % {anio}%"]},
	):
		return []

	creados = []
	for trimestre, mes in enumerate(("01", "04", "07", "10"), start=1):
		creados.append(
			_asiento(
				f"{anio}-{mes}-05",
				f"Transferencia corriente de la Administración Central - T{trimestre} {anio}",
				[
					(cuenta("banco"), monto, 0, cc),
					(cuenta("transferencias_recibidas"), 0, monto, cc),
				],
			)
		)
	return creados


def capital_inicial():
	"""Aporte de capital al inicio de 2025, para que el patrimonio no nazca en cero."""
	if frappe.db.exists(
		"Journal Entry",
		{"company": COMPANY, "docstatus": 1, "user_remark": ["like", "Capital inicial%"]},
	):
		return None

	centros = centros_costo()
	return _asiento(
		"2025-01-01",
		"Capital inicial de la institución",
		[
			(cuenta("banco"), 5_000_000, 0, centros["Dirección Administrativa y Financiera"]),
			(cuenta("capital"), 0, 5_000_000, centros["Dirección Administrativa y Financiera"]),
		],
	)


# --------------------------------------------------------------------------- #
# Ciclo de compras: compromiso → devengado → pagado
# --------------------------------------------------------------------------- #

# (mes, suplidor, artículo, clave de cuenta, centro de costo, monto, hasta dónde llega)
# La última columna deja a propósito documentos en cada etapa del ciclo, para que la
# demo pueda mostrar los tres estados vivos a la vez y no solo operaciones cerradas.
COMPRAS = [
	(2, 0, "SERV-TELECOM", "telefono", "Dirección Administrativa y Financiera", 95_000, "pagado"),
	(3, 1, "SUM-OFICINA", "materiales", "Dirección Administrativa y Financiera", 180_000, "pagado"),
	(4, 0, "SERV-TELECOM", "telefono", "Dirección de Planificación", 42_000, "pagado"),
	(5, 1, "SUM-OFICINA", "materiales", "Consejo Consultivo", 75_000, "pagado"),
	(6, 0, "SERV-TELECOM", "telefono", "Dirección Administrativa y Financiera", 95_000, "pagado"),
	(8, 1, "SUM-OFICINA", "materiales", "Dirección de Planificación", 120_000, "devengado"),
	(9, 1, "SUM-OFICINA", "materiales", "Dirección Administrativa y Financiera", 210_000, "devengado"),
	(10, 0, "SERV-TELECOM", "telefono", "Dirección Administrativa y Financiera", 95_000, "comprometido"),
	(11, 1, "SUM-OFICINA", "materiales", "Consejo Consultivo", 88_000, "comprometido"),
]


def _orden_de_compra(fecha, suplidor, item, cuenta_doc, cc, monto):
	doc = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": COMPANY,
			"supplier": suplidor,
			"transaction_date": fecha,
			"schedule_date": fecha,
			"currency": "DOP",
			"conversion_rate": 1,
			"items": [
				{
					"item_code": item,
					"qty": 1,
					"rate": monto,
					"schedule_date": fecha,
					"expense_account": cuenta_doc,
					"cost_center": cc,
				}
			],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
	return doc


def _facturar(po, fecha, cuenta_doc, cc):
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

	pi = make_purchase_invoice(po.name)
	pi.posting_date = fecha
	pi.set_posting_time = 1
	pi.bill_no = f"B{po.name[-6:]}"
	pi.bill_date = fecha
	# make_purchase_invoice fija el vencimiento contra la fecha de hoy; al mover la
	# factura a su fecha real, el vencimiento quedaría antes que ella y ERPNext lanza.
	pi.due_date = add_days(getdate(fecha), 30)
	pi.credit_to = cuenta("proveedores")
	for item in pi.items:
		item.expense_account = cuenta_doc
		item.cost_center = cc
	pi.flags.ignore_permissions = True
	pi.insert()
	pi.submit()
	return pi


def _pagar(pi, fecha):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Purchase Invoice", pi.name)
	pe.posting_date = fecha
	pe.paid_from = cuenta("banco")
	pe.reference_no = f"TRF-{pi.name[-6:]}"
	pe.reference_date = fecha
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	return pe


def compras(anio):
	"""Genera el ciclo de compras del ejercicio.

	Deja documentos parados en las tres etapas a propósito: una orden solo comprometida
	es lo que demuestra que la disponibilidad presupuestaria baja al emitir la OC y no
	al pagar, que es el punto que el pliego exige controlar.
	"""
	if frappe.db.exists(
		"Purchase Order",
		{"company": COMPANY, "docstatus": 1, "transaction_date": ["between",
		 [f"{anio}-01-01", f"{anio}-12-31"]]},
	):
		return {"omitido": f"{anio} ya tiene órdenes de compra"}

	nombres_suplidores = suplidores()
	centros = centros_costo()
	resumen = {"comprometido": 0, "devengado": 0, "pagado": 0, "omitidas_a_futuro": 0}
	hoy = getdate(nowdate())

	for mes, idx_sup, item, clave, centro, monto, hasta in COMPRAS:
		fecha_po = f"{anio}-{mes:02d}-05"
		# No se siembra nada con fecha futura: una demo con documentos de noviembre
		# cuando estamos en septiembre se nota y resta credibilidad.
		if getdate(fecha_po) > hoy:
			resumen["omitidas_a_futuro"] += 1
			continue
		cuenta_doc = cuenta(clave)
		cc = centros[centro]

		po = _orden_de_compra(fecha_po, nombres_suplidores[idx_sup], item, cuenta_doc, cc, monto)
		resumen["comprometido"] += 1
		if hasta == "comprometido":
			continue

		fecha_pi = f"{anio}-{mes:02d}-18"
		if getdate(fecha_pi) > hoy:
			continue
		pi = _facturar(po, fecha_pi, cuenta_doc, cc)
		resumen["devengado"] += 1
		if hasta == "devengado":
			continue

		fecha_pe = f"{anio}-{mes:02d}-28"
		if getdate(fecha_pe) > hoy:
			continue
		_pagar(pi, fecha_pe)
		resumen["pagado"] += 1

	return resumen


def compra_directa_sin_compromiso(anio):
	"""Una factura sin orden de compra previa.

	El subledger la marca con «Devengado sin compromiso previo», que es la excepción
	que un auditor busca en el sector público. Sin un caso así en la demo, el reporte
	de auditoría no tendría nada que mostrar.
	"""
	marca = f"Compra directa sin orden previa {anio}"
	if frappe.db.exists("Purchase Invoice", {"company": COMPANY, "remarks": marca}):
		return None
	if getdate(f"{anio}-07-14") > getdate(nowdate()):
		return None

	centros = centros_costo()
	pi = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": COMPANY,
			"supplier": suplidores()[0],
			"posting_date": f"{anio}-07-14",
			# Sin set_posting_time, ERPNext pisa la fecha con la de hoy.
			"set_posting_time": 1,
			"bill_no": f"URG-{anio}-001",
			"bill_date": f"{anio}-07-14",
			"due_date": f"{anio}-08-13",
			"credit_to": cuenta("proveedores"),
			"currency": "DOP",
			"conversion_rate": 1,
			"remarks": marca,
			"items": [
				{
					"item_code": "SUM-OFICINA",
					"qty": 1,
					"rate": 36_000,
					"expense_account": cuenta("materiales"),
					"cost_center": centros["Dirección Administrativa y Financiera"],
				}
			],
		}
	)
	pi.flags.ignore_permissions = True
	pi.insert()
	pi.submit()
	return pi.name


# --------------------------------------------------------------------------- #
# Personal y nómina
# --------------------------------------------------------------------------- #

# (nombre, apellido, cédula, cargo, sueldo mensual, centro de costo)
PERSONAL = [
	("Altagracia", "Reyes Peña", "00101234567", "Directora Administrativa y Financiera",
	 145_000, "Dirección Administrativa y Financiera"),
	("Rafael", "Mejía Santos", "00112345678", "Encargado de Contabilidad",
	 98_000, "Dirección Administrativa y Financiera"),
	("Yokasta", "Núñez Abreu", "00123456789", "Analista de Presupuesto",
	 72_000, "Dirección Administrativa y Financiera"),
	("Ernesto", "Guzmán Polanco", "00134567890", "Encargado de Planificación",
	 105_000, "Dirección de Planificación"),
	("Mariela", "Cabrera Jiménez", "00145678901", "Secretaria del Consejo",
	 65_000, "Consejo Consultivo"),
]

COMPONENTE_SUELDO = "Sueldo Base"
ESTRUCTURA = "Escala Salarial CES"


def _lista_feriados():
	"""Una sola lista de feriados que cubre todos los ejercicios de la demo.

	Frappe resuelve la lista por empleado (o el default de la institución) y exige que
	cubra el período del volante Y la fecha de registro. Con una lista por año, un
	volante de 2025 registrado hoy falla. Una sola lista multianual lo evita.
	"""
	nombre = f"Feriados RD {ANIOS[0]}-{ANIOS[-1]}"
	if frappe.db.exists("Holiday List", nombre):
		return nombre

	feriados = []
	for anio in range(ANIOS[0], ANIOS[-1] + 2):
		feriados += [
			{"holiday_date": f"{anio}-01-01", "description": "Año Nuevo"},
			{"holiday_date": f"{anio}-01-21", "description": "Nuestra Señora de la Altagracia"},
			{"holiday_date": f"{anio}-01-26", "description": "Día de Duarte"},
			{"holiday_date": f"{anio}-02-27", "description": "Día de la Independencia"},
			{"holiday_date": f"{anio}-05-01", "description": "Día del Trabajo"},
			{"holiday_date": f"{anio}-08-16", "description": "Día de la Restauración"},
			{"holiday_date": f"{anio}-09-24", "description": "Nuestra Señora de las Mercedes"},
			{"holiday_date": f"{anio}-11-06", "description": "Día de la Constitución"},
			{"holiday_date": f"{anio}-12-25", "description": "Navidad"},
		]

	doc = frappe.get_doc(
		{
			"doctype": "Holiday List",
			"holiday_list_name": nombre,
			"from_date": f"{ANIOS[0]}-01-01",
			"to_date": f"{ANIOS[-1] + 1}-12-31",
			"holidays": feriados,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	frappe.db.set_value("Company", COMPANY, "default_holiday_list", doc.name)
	_asignar_feriados(doc.name)
	return doc.name


def _asignar_feriados(lista):
	"""hrms v16 resuelve los feriados por `Holiday List Assignment`, no por el campo
	del empleado ni el default de la Company. Una asignación a nivel de institución
	cubre a toda la plantilla, presente y futura."""
	if frappe.db.exists(
		"Holiday List Assignment",
		{"holiday_list": lista, "assigned_to": COMPANY, "docstatus": 1},
	):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Holiday List Assignment",
			"holiday_list": lista,
			"applicable_for": "Company",
			"assigned_to": COMPANY,
			"from_date": f"{ANIOS[0]}-01-01",
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()


def _designacion(nombre):
	return _existe_o_crea("Designation", {"designation_name": nombre},
	                      {"designation_name": nombre})


def empleados():
	"""Plantilla de la institución, con cédulas de dígito verificador válido."""
	if not frappe.db.exists("Gender", "Femenino"):
		for g in ("Femenino", "Masculino"):
			if not frappe.db.exists("Gender", g):
				frappe.get_doc({"doctype": "Gender", "gender": g}).insert(
					ignore_permissions=True
				)

	centros = centros_costo()
	feriados = _lista_feriados()
	creados = []

	for nombre, apellido, cedula, cargo, _sueldo, centro in PERSONAL:
		existente = frappe.db.get_value(
			"Employee", {"employee_name": f"{nombre} {apellido}", "company": COMPANY}, "name"
		)
		if existente:
			creados.append(existente)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": nombre,
				"last_name": apellido,
				"company": COMPANY,
				"gender": "Femenino" if nombre[-1] in "ay" else "Masculino",
				"date_of_birth": "1985-06-15",
				"date_of_joining": "2024-01-15",
				"status": "Active",
				"designation": _designacion(cargo),
				"payroll_cost_center": centros[centro],
				"holiday_list": feriados,
				"bank_name": "Banreservas",
				"bank_ac_no": f"96{cedula[-8:]}",
				"custom_cedula": cedula,
			}
		)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
		creados.append(doc.name)

	return creados


def componentes_salariales():
	"""Un devengo de sueldo y la deducción de préstamos bancarios."""
	from tz_gobierno.nomina import asegurar_componente

	if not frappe.db.exists("Salary Component", COMPONENTE_SUELDO):
		doc = frappe.get_doc(
			{
				"doctype": "Salary Component",
				"salary_component": COMPONENTE_SUELDO,
				"salary_component_abbr": "SB",
				"type": "Earning",
				"accounts": [{"company": COMPANY, "account": cuenta("sueldos")}],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()

	deduccion = asegurar_componente()
	comp = frappe.get_doc("Salary Component", deduccion)
	if not any(a.company == COMPANY for a in comp.accounts):
		comp.append("accounts", {"company": COMPANY, "account": cuenta("nomina_por_pagar")})
		comp.flags.ignore_permissions = True
		comp.save()

	return [COMPONENTE_SUELDO, deduccion]


def estructura_salarial():
	"""Estructura única: el sueldo base viene de la asignación de cada empleado."""
	componentes_salariales()

	if frappe.db.exists("Salary Structure", ESTRUCTURA):
		return ESTRUCTURA

	doc = frappe.get_doc(
		{
			"doctype": "Salary Structure",
			"name": ESTRUCTURA,
			"company": COMPANY,
			"currency": "DOP",
			"payroll_frequency": "Monthly",
			"payment_account": cuenta("banco"),
			"earnings": [
				{
					"salary_component": COMPONENTE_SUELDO,
					"abbr": "SB",
					"amount_based_on_formula": 1,
					"formula": "base",
				}
			],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
	return doc.name


def asignaciones_salariales():
	"""Asigna la estructura y el sueldo base de cada empleado desde 2025."""
	estructura = estructura_salarial()
	nombres = empleados()
	asignados = []

	for docname, (_n, _a, _c, _cargo, sueldo, _centro) in zip(nombres, PERSONAL):
		if frappe.db.exists(
			"Salary Structure Assignment",
			{"employee": docname, "salary_structure": estructura, "docstatus": 1},
		):
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Salary Structure Assignment",
				"employee": docname,
				"salary_structure": estructura,
				"from_date": "2025-01-01",
				"company": COMPANY,
				"base": sueldo,
				"currency": "DOP",
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
		asignados.append(doc.name)

	return asignados


# (índice en PERSONAL, banco, monto, cuota, cuotas, cuotas ya pagadas al inicio)
PRESTAMOS = [
	(1, "Banreservas", 240_000, 10_000, 24, 0),
	(3, "Banco Popular", 150_000, 6_250, 24, 0),
]


def prestamos_personal():
	"""Préstamos que la institución garantiza y descuenta por nómina.

	El pasivo es del banco, no del CES: aquí solo se trackea para retener la cuota.
	"""
	nombres = empleados()
	creados = []

	for idx, banco, monto, cuota, cuotas, pagadas in PRESTAMOS:
		employee = nombres[idx]
		existente = frappe.db.get_value(
			"Prestamo Bancario Empleado", {"employee": employee, "banco": banco}
		)
		if existente:
			creados.append(existente)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Prestamo Bancario Empleado",
				"employee": employee,
				"company": COMPANY,
				"banco": banco,
				"fecha_inicio": "2025-01-15",
				"monto_prestamo": monto,
				"cuota_mensual": cuota,
				"numero_cuotas": cuotas,
				"cuotas_pagadas": pagadas,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		creados.append(doc.name)

	return creados


def _corrida_de_nomina(anio, mes):
	"""Una corrida mensual: crea los volantes, los confirma y devuelve el Payroll Entry."""
	from frappe.utils import get_last_day

	inicio = f"{anio}-{mes:02d}-01"
	fin = str(get_last_day(inicio))
	centros = centros_costo()

	# Un borrador de una corrida anterior se retoma en vez de devolverse tal cual:
	# devolverlo sin confirmar dejaba corridas vacías que parecían haber funcionado.
	existente = frappe.db.get_value(
		"Payroll Entry",
		{"company": COMPANY, "start_date": inicio, "docstatus": ["<", 2]},
		["name", "docstatus"],
		as_dict=True,
	)
	if existente and existente.docstatus == 1:
		return existente.name

	if existente:
		pe = frappe.get_doc("Payroll Entry", existente.name)
	else:
		pe = frappe.get_doc(
		{
			"doctype": "Payroll Entry",
			"company": COMPANY,
			"posting_date": fin,
			"payroll_frequency": "Monthly",
			"start_date": inicio,
			"end_date": fin,
			"payment_account": cuenta("banco"),
			# No se autocompleta desde la Company al insertar por código.
			"payroll_payable_account": cuenta("nomina_por_pagar"),
			"cost_center": centros["Dirección Administrativa y Financiera"],
			"exchange_rate": 1,
			"currency": "DOP",
			}
		)
		pe.flags.ignore_permissions = True
		pe.insert()

	pe.fill_employee_details()
	pe.save()
	# on_submit hace un reload() interno, así que el documento tiene que estar
	# realmente en la base y no solo en la transacción abierta.
	frappe.db.commit()

	# Con pocos empleados los volantes se crean en línea; el flag fuerza el modo
	# síncrono para que la siembra sea determinista y no dependa del worker.
	frappe.flags.in_test = True
	try:
		pe.submit()
		pe.reload()
		pe.submit_salary_slips()
	finally:
		frappe.flags.in_test = False

	frappe.db.commit()
	return pe.name


def nomina(anio):
	"""Corridas mensuales del ejercicio, sin pasarse de la fecha de hoy."""
	prestamos_personal()
	asignaciones_salariales()

	hoy = getdate(nowdate())
	creadas, omitidas = [], 0

	for mes in range(1, 13):
		from frappe.utils import get_last_day

		fin = getdate(get_last_day(f"{anio}-{mes:02d}-01"))
		if fin > hoy:
			omitidas += 1
			continue
		creadas.append(_corrida_de_nomina(anio, mes))

	return {"corridas": len(creadas), "omitidas_a_futuro": omitidas}


# --------------------------------------------------------------------------- #
# Activos fijos y depreciación
# --------------------------------------------------------------------------- #

CATEGORIA_ACTIVO = "Mobiliario y Equipo de Oficina"
UBICACION = "Sede CES - Santo Domingo"

# (nombre, código de Bienes Nacionales, costo, fecha de puesta en uso, vida en años)
ACTIVOS = [
	("Escritorio ejecutivo en caoba", "BN-CES-000101", 85_000, "2025-02-10", 10),
	("Juego de sillas de conferencia (12)", "BN-CES-000102", 132_000, "2025-02-10", 10),
	("Archivo modular de 4 gavetas", "BN-CES-000103", 46_000, "2025-05-20", 10),
	("Planta eléctrica de emergencia 20KW", "BN-CES-000104", 480_000, "2025-08-01", 8),
	("Mobiliario sala de sesiones", "BN-CES-000105", 260_000, "2026-03-15", 10),
]


def categoria_activo():
	"""Categoría con las cuentas DIGECOG de costo, depreciación acumulada y gasto."""
	if frappe.db.exists("Asset Category", CATEGORIA_ACTIVO):
		return CATEGORIA_ACTIVO

	doc = frappe.get_doc(
		{
			"doctype": "Asset Category",
			"asset_category_name": CATEGORIA_ACTIVO,
			# Línea recta: es el método que usa el sector público dominicano.
			"accounts": [
				{
					"company_name": COMPANY,
					"fixed_asset_account": cuenta("mobiliario_costo"),
					"accumulated_depreciation_account": cuenta("mobiliario_deprec_acum"),
					"depreciation_expense_account": cuenta("mobiliario_deprec_gasto"),
				}
			],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def ubicacion():
	return _existe_o_crea("Location", {"location_name": UBICACION},
	                      {"location_name": UBICACION})


def articulo_activo_fijo():
	"""ERPNext exige un Item por activo. Uno genérico de activo fijo alcanza:
	lo que identifica al bien en el sector público es su código de Bienes Nacionales,
	no un catálogo de artículos."""
	codigo = "ACT-MOBILIARIO"
	return _existe_o_crea(
		"Item",
		{"item_code": codigo},
		{
			"item_code": codigo,
			"item_name": "Mobiliario y equipo de oficina",
			"item_group": "All Item Groups",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_fixed_asset": 1,
			"asset_category": categoria_activo(),
			"auto_create_assets": 0,
		},
	)


def activos():
	"""Alta de activos con depreciación en línea recta, sin pasar de la fecha de hoy."""
	categoria = categoria_activo()
	lugar = ubicacion()
	item = articulo_activo_fijo()
	centros = centros_costo()
	hoy = getdate(nowdate())
	creados, omitidos = [], 0

	for nombre, codigo_bn, costo, desde, vida in ACTIVOS:
		if getdate(desde) > hoy:
			omitidos += 1
			continue

		existente = frappe.db.get_value("Asset", {"asset_name": nombre, "company": COMPANY})
		if existente:
			creados.append(existente)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Asset",
				"asset_name": nombre,
				"company": COMPANY,
				"asset_category": categoria,
				"item_code": item,
				"location": lugar,
				"cost_center": centros["Dirección Administrativa y Financiera"],
				"purchase_date": desde,
				"available_for_use_date": desde,
				"gross_purchase_amount": costo,
				"net_purchase_amount": costo,
				"asset_quantity": 1,
				"is_existing_asset": 1,
				"calculate_depreciation": 1,
				"codigo_bienes_nacionales": codigo_bn,
				"finance_books": [
					{
						"depreciation_method": "Straight Line",
						"total_number_of_depreciations": vida * 12,
						"frequency_of_depreciation": 1,
						"depreciation_start_date": str(frappe.utils.get_last_day(desde)),
						# Valor residual simbólico: DIGECOG deprecia hasta 1 peso.
						"expected_value_after_useful_life": 1,
					}
				],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
		_contabilizar_alta_de_activo(doc, costo, desde, centros)
		creados.append(doc.name)

	return {"creados": len(creados), "omitidos_a_futuro": omitidos, "activos": creados}


def _contabilizar_alta_de_activo(asset, costo, fecha, centros):
	"""Registra la adquisición en el mayor.

	Los activos se dan de alta con `is_existing_asset`, que NO genera asiento: ERPNext
	asume que el costo ya está en los libros por saldos de apertura. Aquí no lo está,
	así que sin este asiento la depreciación iría contra una cuenta de costo vacía y
	Propiedad, planta y equipo saldría NEGATIVA en el Estado de Situación Financiera.
	"""
	marca = f"Adquisición de activo {asset.name}"
	if frappe.db.exists(
		"Journal Entry", {"company": COMPANY, "user_remark": marca, "docstatus": 1}
	):
		return None

	return _asiento(
		fecha,
		marca,
		[
			(cuenta("mobiliario_costo"), costo, 0,
			 centros["Dirección Administrativa y Financiera"]),
			(cuenta("banco"), 0, costo, centros["Dirección Administrativa y Financiera"]),
		],
	)


def depreciacion():
	"""Registra los asientos de depreciación mensual devengados hasta hoy."""
	from erpnext.assets.doctype.asset.depreciation import post_depreciation_entries

	post_depreciation_entries(date=nowdate())
	frappe.db.commit()

	return frappe.db.count(
		"Journal Entry", {"company": COMPANY, "voucher_type": "Depreciation Entry"}
	)


# --------------------------------------------------------------------------- #
# Módulos secundarios
# --------------------------------------------------------------------------- #


def tarjetas_credito(anio):
	"""Un lote de consumos de tarjeta corporativa por semestre, con su asiento."""
	centros = centros_costo()
	cc = centros["Dirección Administrativa y Financiera"]
	hoy = getdate(nowdate())
	creados = []

	lotes = [
		(f"{anio}-03", f"{anio}-03-31", [
			("Estación de servicio Sigma", 12_400, "materiales"),
			("Librería Nacional", 8_750, "materiales"),
			("Claro - recarga corporativa", 6_200, "telefono"),
		]),
		(f"{anio}-09", f"{anio}-09-30", [
			("Hotel Jaragua - alojamiento misión", 34_500, "materiales"),
			("Supermercado Nacional - cafetería", 9_800, "materiales"),
		]),
	]

	for periodo, corte, consumos in lotes:
		if getdate(corte) > hoy:
			continue
		nombre = f"TC-7788-{periodo}"
		if frappe.db.exists("Lote Tarjeta Credito", nombre):
			creados.append(nombre)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Lote Tarjeta Credito",
				"banco": "Banreservas",
				"ultimos_4_digitos": "7788",
				"company": COMPANY,
				"periodo": periodo,
				"fecha_corte": corte,
				"cuenta_tarjeta": cuenta("tarjeta"),
				"consumos": [
					{
						"fecha": corte,
						"comercio": comercio,
						"monto": monto,
						"account": cuenta(clave),
						"cost_center": cc,
					}
					for comercio, monto, clave in consumos
				],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.generar_asiento()
		doc.reload()
		doc.marcar_conciliado()
		creados.append(doc.name)

	return creados


def encuesta_clima():
	"""Encuesta de clima laboral respondida por toda la plantilla."""
	titulo = "Clima laboral 2026"
	if frappe.db.exists("Encuesta", titulo):
		return titulo

	doc = frappe.get_doc(
		{
			"doctype": "Encuesta",
			"titulo": titulo,
			"descripcion": "Medición anual de clima laboral del personal del Consejo.",
			"activa": 1,
			"fecha_inicio": "2026-06-01",
			"fecha_fin": "2026-06-30",
			"preguntas": [
				{"texto": "¿Cómo calificas el ambiente de trabajo?",
				 "tipo_respuesta": "Escala 1-5"},
				{"texto": "¿Cómo calificas la comunicación con tu supervisor?",
				 "tipo_respuesta": "Escala 1-5"},
				{"texto": "¿Qué modalidad de trabajo prefieres?",
				 "tipo_respuesta": "Selección múltiple",
				 "opciones": "Presencial\nHíbrida\nRemota"},
				{"texto": "¿Qué mejorarías de la institución?",
				 "tipo_respuesta": "Texto abierto"},
			],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()

	respuestas = [
		(5, 4, "Híbrida", "Más espacios de formación continua."),
		(4, 5, "Presencial", "Mejorar el mobiliario de las oficinas."),
		(3, 3, "Híbrida", "Agilizar los procesos de compra."),
		(5, 5, "Remota", "Todo bien, seguir así."),
		(4, 4, "Híbrida", "Más reuniones de seguimiento."),
	]

	for ambiente, comunicacion, modalidad, comentario in respuestas:
		r = frappe.get_doc(
			{
				"doctype": "Respuesta Encuesta",
				"encuesta": doc.name,
				"anonima": 1,
				"fecha": "2026-06-15",
				"respuestas": [
					{"pregunta": doc.preguntas[0].texto, "respuesta": str(ambiente)},
					{"pregunta": doc.preguntas[1].texto, "respuesta": str(comunicacion)},
					{"pregunta": doc.preguntas[2].texto, "respuesta": modalidad},
					{"pregunta": doc.preguntas[3].texto, "respuesta": comentario},
				],
			}
		)
		r.flags.ignore_permissions = True
		r.insert()

	return doc.name


NOTAS = [
	("Entidad económica",
	 "El Consejo Económico y Social (CES) es un órgano consultivo del Estado dominicano, "
	 "creado por la Ley 142-15, con personalidad jurídica y patrimonio propio."),
	("Base de presentación",
	 "Los presentes estados financieros se preparan conforme al Manual para la Elaboración "
	 "de Estados Financieros de la DIGECOG y al Catálogo de Cuentas Contables vigente."),
	("Moneda funcional y de presentación",
	 "La moneda funcional y de presentación es el peso dominicano (RD$)."),
	("Uso de estimados y juicios",
	 "La preparación de los estados financieros requiere estimaciones de la administración, "
	 "principalmente en la vida útil de la propiedad, planta y equipo."),
	("Base de medición",
	 "Los estados financieros se preparan sobre la base del costo histórico, salvo las "
	 "partidas que la normativa exija medir de otra forma."),
	("Resumen de políticas contables",
	 "La depreciación se calcula por el método de línea recta sobre la vida útil estimada. "
	 "Los ingresos por transferencias se reconocen cuando se hacen exigibles."),
]


def notas_estados_financieros(anio):
	creadas = []
	for orden, (tipo, contenido) in enumerate(NOTAS, start=1):
		existente = frappe.db.get_value(
			"Nota Estado Financiero",
			{"company": COMPANY, "fiscal_year": str(anio), "tipo": tipo},
		)
		if existente:
			creadas.append(existente)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Nota Estado Financiero",
				"company": COMPANY,
				"fiscal_year": str(anio),
				"tipo": tipo,
				"orden": orden,
				"contenido": f"<p>{contenido}</p>",
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		creadas.append(doc.name)

	return creadas


def tramites_de_pago(anio):
	"""Solicitudes de trámite de pago en distintos estados del flujo."""
	hoy = getdate(nowdate())
	lineas = frappe.get_all(
		"Linea Presupuestaria",
		filters={"company": COMPANY, "fiscal_year": str(anio)},
		pluck="name",
		limit=3,
	)
	if not lineas:
		return []

	solicitudes = [
		(2, "Bienes y servicios", "Suministros de Oficina del Caribe SRL",
		 "Pago de suministros de oficina del primer trimestre", 180_000, "Pagado"),
		(5, "Nómina", "Personal fijo del Consejo",
		 "Trámite de pago de nómina de mayo", 485_000, "Pagado"),
		(8, "Bienes y servicios", "Servicios Tecnológicos Quisqueya SRL",
		 "Mantenimiento de la plataforma tecnológica", 120_000, "Aprobado"),
		(9, "Otro", "Mobiliario Corporativo Duarte SRL",
		 "Adquisición de mobiliario para sala de sesiones", 260_000, "En revisión"),
	]

	creados = []
	for mes, tipo, beneficiario, concepto, monto, estado in solicitudes:
		fecha = f"{anio}-{mes:02d}-10"
		if getdate(fecha) > hoy:
			continue
		if frappe.db.exists(
			"Solicitud Tramite Pago",
			{"company": COMPANY, "fecha": fecha, "beneficiario": beneficiario},
		):
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Solicitud Tramite Pago",
				"company": COMPANY,
				"tipo_tramite": tipo,
				"fecha": fecha,
				"linea_presupuestaria": lineas[0],
				"tipo_orden_pago": "Transferencia" if tipo != "Otro" else "Cheque",
				"numero_orden": f"OP-{anio}-{mes:03d}",
				"beneficiario": beneficiario,
				"concepto": concepto,
				"monto": monto,
				"funcionario_autorizante": "Altagracia Reyes Peña",
				"estado": estado,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		creados.append(doc.name)

	return creados


# --------------------------------------------------------------------------- #
# Orquestador
# --------------------------------------------------------------------------- #


@frappe.whitelist()
def ejecutar():
	"""Siembra todo, en el orden en que las dependencias lo exigen."""
	from tz_gobierno.setup import banreservas
	from tz_gobierno.setup.sitio import sembrar_masters

	resumen = {}

	sembrar_masters()
	resumen["anios_fiscales"] = anios_fiscales()
	preparar_company()
	resumen["centros_costo"] = len(centros_costo())
	resumen["suplidores"] = len(suplidores())
	resumen["articulos"] = len(articulos())
	_lista_feriados()
	resumen["empleados"] = len(empleados())
	resumen["banco_nomina"] = banreservas.crear(COMPANY)
	resumen["capital_inicial"] = capital_inicial()
	resumen["encuesta"] = encuesta_clima()

	for anio in ANIOS:
		resumen[f"{anio}"] = {
			"presupuesto": len(presupuesto(anio)),
			"modificacion": modificacion_presupuestaria(anio),
			"financiamiento": len(financiamiento(anio)),
			"compras": compras(anio),
			"compra_directa": compra_directa_sin_compromiso(anio),
			"nomina": nomina(anio),
			"tarjetas": len(tarjetas_credito(anio)),
			"notas": len(notas_estados_financieros(anio)),
			"tramites": len(tramites_de_pago(anio)),
		}

	resumen["activos"] = activos()
	resumen["asientos_depreciacion"] = depreciacion()

	frappe.db.commit()
	return resumen


def nomina_en_presupuesto():
	"""Registra en el subledger la nómina ya confirmada.

	El hook de `Salary Slip` solo actúa sobre volantes nuevos; esto recorre los que
	ya estaban para que la ejecución presupuestaria de remuneraciones refleje la
	realidad y no aparezca en 0% en el Estado de Comparación.
	"""
	from tz_gobierno.nomina import registrar_devengado_nomina, registrar_pago_nomina
	from tz_gobierno.presupuesto import ETAPA_DEVENGADO, _movimientos_vivos_de

	devengados, pagados = 0, 0

	for slip in frappe.get_all(
		"Salary Slip", filters={"company": COMPANY, "docstatus": 1}, pluck="name"
	):
		ya = frappe.db.exists(
			"Movimiento Presupuestario",
			{"referencia_doctype": "Salary Slip", "referencia_name": slip},
		)
		if ya:
			continue
		registrar_devengado_nomina(frappe.get_doc("Salary Slip", slip))
		devengados += 1

	for corrida in frappe.get_all(
		"Payroll Entry", filters={"company": COMPANY, "docstatus": 1}, pluck="name"
	):
		resultado = registrar_pago_nomina(corrida)
		pagados += resultado["lineas_afectadas"]

	frappe.db.commit()
	return {"volantes_devengados": devengados, "lineas_pagadas": pagados}
