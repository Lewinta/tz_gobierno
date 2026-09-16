# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Agregación de resultados de encuestas (§7 del spec).

Cada tipo de pregunta se agrega distinto: las de selección múltiple por conteo de cada
opción, las de escala 1-5 por promedio, y las de texto abierto no se agregan — se
listan, porque promediar texto no significa nada.
"""

import frappe
from frappe import _
from frappe.utils import flt

SELECCION_MULTIPLE = "Selección múltiple"
ESCALA = "Escala 1-5"
TEXTO_ABIERTO = "Texto abierto"


def resultados(encuesta):
	"""Resultados agregados por pregunta.

	Devuelve una lista de dicts con `pregunta`, `tipo`, `total_respuestas` y, según el
	tipo, `conteos` / `promedio` / `textos`.
	"""
	doc = frappe.get_doc("Encuesta", encuesta)

	detalles = frappe.db.sql(
		"""
		select d.pregunta, d.tipo_respuesta, d.respuesta
		from `tabRespuesta Encuesta Detalle` d
		join `tabRespuesta Encuesta` r on r.name = d.parent
		where r.encuesta = %s
		""",
		encuesta,
		as_dict=True,
	)

	por_pregunta = {}
	for detalle in detalles:
		por_pregunta.setdefault(detalle.pregunta, []).append(detalle.respuesta)

	salida = []
	for pregunta in doc.preguntas:
		respuestas = [r for r in por_pregunta.get(pregunta.texto, []) if r not in (None, "")]
		fila = {
			"pregunta": pregunta.texto,
			"tipo": pregunta.tipo_respuesta,
			"total_respuestas": len(respuestas),
		}

		if pregunta.tipo_respuesta == SELECCION_MULTIPLE:
			conteos = {}
			for opcion in _opciones(pregunta):
				conteos[opcion] = 0
			for respuesta in respuestas:
				conteos[respuesta] = conteos.get(respuesta, 0) + 1
			fila["conteos"] = conteos

		elif pregunta.tipo_respuesta == ESCALA:
			valores = [flt(r) for r in respuestas if _es_numero(r)]
			fila["promedio"] = (sum(valores) / len(valores)) if valores else 0.0
			fila["conteos"] = {str(n): sum(1 for v in valores if int(v) == n) for n in range(1, 6)}

		else:
			fila["textos"] = respuestas

		salida.append(fila)

	return salida


def _opciones(pregunta):
	return [o.strip() for o in (pregunta.opciones or "").splitlines() if o.strip()]


def _es_numero(valor):
	try:
		float(valor)
		return True
	except (TypeError, ValueError):
		return False


@frappe.whitelist()
def resumen(encuesta):
	"""Entrypoint para la UI y para `bench execute`."""

	lineas = []
	for fila in resultados(encuesta):
		if fila["tipo"] == ESCALA:
			lineas.append(f"{fila['pregunta']}: promedio {fila['promedio']:.2f} "
			              f"({fila['total_respuestas']} respuestas)")
		elif fila["tipo"] == SELECCION_MULTIPLE:
			detalle = ", ".join(f"{k}={v}" for k, v in fila["conteos"].items())
			lineas.append(f"{fila['pregunta']}: {detalle}")
		else:
			lineas.append(f"{fila['pregunta']}: {fila['total_respuestas']} respuestas de texto")
	return "\n".join(lineas)


def validar_respuesta(doc, method=None):
	"""Las respuestas tienen que corresponder a preguntas reales de la encuesta."""
	encuesta = frappe.get_doc("Encuesta", doc.encuesta)
	validas = {p.texto: p for p in encuesta.preguntas}

	for detalle in doc.respuestas:
		pregunta = validas.get(detalle.pregunta)
		if not pregunta:
			frappe.throw(
				_("La pregunta «{0}» no pertenece a la encuesta {1}.").format(
					detalle.pregunta, doc.encuesta
				)
			)

		detalle.tipo_respuesta = pregunta.tipo_respuesta

		if pregunta.tipo_respuesta == ESCALA and detalle.respuesta:
			if not _es_numero(detalle.respuesta) or not 1 <= flt(detalle.respuesta) <= 5:
				frappe.throw(
					_("«{0}» es de escala 1-5; «{1}» no es un valor válido.").format(
						pregunta.texto, detalle.respuesta
					)
				)

		if pregunta.tipo_respuesta == SELECCION_MULTIPLE and detalle.respuesta:
			opciones = _opciones(pregunta)
			if opciones and detalle.respuesta not in opciones:
				frappe.throw(
					_("«{0}» no es una opción de «{1}». Opciones: {2}").format(
						detalle.respuesta, pregunta.texto, ", ".join(opciones)
					)
				)

	if doc.anonima:
		# Una encuesta anónima que guarda el empleado no es anónima.
		doc.employee = None
