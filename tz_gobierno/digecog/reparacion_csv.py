# Copyright (c) 2026, TZCode S.R.L. and contributors
# For license information, please see license.txt
"""Reparación de un defecto de extracción del PDF en plan_de_cuentas_digecog.csv.

PROBLEMA DETECTADO (2026-09-16, no documentado en el spec CES-0009)
-------------------------------------------------------------------
El spec afirma que el único problema de integridad del CSV es la cuenta huérfana
`4.9.99`. Al importar se encontró un segundo defecto, mayor:

  40 filas (23 de nivel 6 y 17 de nivel 7) tienen su columna `nombre_cuenta`
  corrupta: la extracción del PDF concatenó dentro de ese campo las filas que le
  seguían en la tabla. El contenido real de esas celdas es

      "<nombre propio> <codigo> <nombre> <S|N> [<codigo> <nombre> <S|N> ...]"

  Los 80 códigos embebidos no son todos hijos de la fila que los contiene: 51 lo
  son y 29 son hermanos. Es simplemente "la fila siguiente del documento", así que
  el padre de cada cuenta recuperada se deriva de su **propio código** (quitando el
  último segmento), no de la fila donde apareció.

  Consecuencia: **80 cuentas de nivel 7 no existen como fila propia en el CSV**.
  El plan no tiene 3,595 cuentas completas; tiene 3,595 filas de las cuales 40
  están corruptas, y faltan 80 cuentas. El total real es 3,675.

Esto importa porque la cláusula 16.1.1 del pliego es excluyente y el plan de
cuentas DIGECOG es de uso obligatorio: importar un plan al que le faltan 80
cuentas y con 40 nombres corruptos es exactamente el tipo de no conformidad que
descalifica.

ALCANCE DE ESTA REPARACIÓN
--------------------------
Esto es un **rescate del texto ya degradado**, no una re-extracción del PDF
oficial (que no está disponible en el bench). El parser es deliberadamente
estricto: si una fila no encaja exactamente en la forma esperada, lanza en vez de
adivinar. Nunca produce una recuperación silenciosa y dudosa.

PENDIENTE: validar las 80 cuentas recuperadas contra el PDF oficial de DIGECOG
antes de la demo. Mientras tanto quedan marcadas y son listables con
`cuentas_recuperadas()`.
"""

import re

# Un código DIGECOG: dígitos separados por puntos, al menos dos segmentos.
RE_CODIGO = re.compile(r"(?<![\d.])(\d+(?:\.\d+)+)(?![\d.])")

# Cierre de cada hijo embebido: el flag `imputable` de su propia fila.
RE_FLAG_FINAL = re.compile(r"\s+([SN])\s*$")


class ReparacionError(Exception):
	"""El texto corrupto no encaja en la forma esperada; no se adivina."""


def _normalizar(texto):
	return " ".join(texto.split())


def fila_esta_corrupta(fila):
	"""True si `nombre_cuenta` trae códigos DIGECOG embebidos.

	Se ignora el primer carácter al buscar para no confundir un nombre que
	legítimamente empiece con algo numérico.
	"""
	return bool(RE_CODIGO.search(_normalizar(fila["nombre_cuenta"])[1:]))


def reparar_fila(fila):
	"""Separa una fila corrupta en (nombre_limpio, [hijos recuperados]).

	Cada hijo recuperado es un dict con las mismas columnas que el CSV.
	Lanza ReparacionError si la forma no es la esperada.
	"""
	texto = _normalizar(fila["nombre_cuenta"])
	codigo_padre = fila["codigo"].strip()

	partes = RE_CODIGO.split(texto)
	# split con un grupo de captura da: [texto_antes, cod1, texto1, cod2, texto2, ...]
	nombre_limpio = partes[0].strip()
	if not nombre_limpio:
		raise ReparacionError(f"{codigo_padre}: no se pudo aislar el nombre propio")

	hijos = []
	for i in range(1, len(partes), 2):
		codigo_hijo = partes[i]
		resto = partes[i + 1] if i + 1 < len(partes) else ""

		m = RE_FLAG_FINAL.search(resto)
		if m:
			imputable = m.group(1)
			nombre_hijo = resto[: m.start()].strip()
		else:
			# Último hijo de la celda: el flag puede haberse perdido en el corte.
			# Los niveles 7 del plan DIGECOG son siempre imputables.
			imputable = "S"
			nombre_hijo = resto.strip()

		if not nombre_hijo:
			raise ReparacionError(f"{codigo_padre}: el hijo {codigo_hijo} quedó sin nombre")

		nivel = len(codigo_hijo.split("."))
		if nivel != 7:
			# Todo lo recuperado hasta ahora es nivel 7 (hoja imputable). Otro nivel
			# significaría una forma de corrupción distinta que no se debe adivinar.
			raise ReparacionError(
				f"{codigo_padre}: el código embebido {codigo_hijo} sería nivel {nivel}, "
				"no 7; forma inesperada"
			)

		hijos.append(
			{
				"codigo": codigo_hijo,
				"nombre_cuenta": nombre_hijo,
				"imputable": imputable,
				"is_group": "0",
				"nivel": str(nivel),
				# El padre se deriva del propio código: los embebidos son "la fila
				# siguiente del PDF", que puede ser hermana de la fila contenedora.
				"codigo_padre": codigo_hijo.rsplit(".", 1)[0],
				"root_type": fila["root_type"],
				"_recuperada": True,
				"_hallada_en": codigo_padre,
			}
		)

	if not hijos:
		raise ReparacionError(f"{codigo_padre}: marcada como corrupta pero no se extrajo ningún hijo")

	return nombre_limpio, hijos


def normalizar_is_group(filas):
	"""Marca como grupo toda cuenta que tenga hijos, aunque el CSV diga lo contrario.

	Defecto independiente del anterior, y presente también en el CSV crudo: 18
	cuentas vienen con `imputable=S` / `is_group=0` pero tienen hijos en el plan.
	ERPNext no puede modelar un ledger con hijos — `Account.validate_parent()` lanza
	"Parent account can not be a ledger" — así que la jerarquía manda sobre el flag.

	No se pierde capacidad de registro: la regla de DIGECOG es imputar siempre al
	nivel más bajo, que son justamente los hijos de estas cuentas.

	Muta `filas` in situ y devuelve la lista de códigos reagrupados.
	"""
	con_hijos = {f["codigo_padre"].strip() for f in filas if f["codigo_padre"].strip()}
	regrupadas = []

	for fila in filas:
		codigo = fila["codigo"].strip()
		if codigo in con_hijos and str(fila["is_group"]) == "0":
			fila["is_group"] = "1"
			fila["imputable"] = "N"
			regrupadas.append(codigo)

	return regrupadas


def reparar(filas):
	"""Aplica la reparación a la lista completa de filas del CSV.

	Devuelve (filas_reparadas, informe). Las filas corruptas quedan con el nombre
	limpio y los hijos recuperados se agregan como filas nuevas.
	"""
	codigos = {f["codigo"].strip() for f in filas}
	salida = []
	recuperadas = []
	limpiadas = []

	for fila in filas:
		if not fila_esta_corrupta(fila):
			# Copia: normalizar_is_group() muta, y no debe tocar la lista del llamador.
			salida.append(dict(fila))
			continue

		nombre_limpio, hijos = reparar_fila(fila)
		limpiadas.append((fila["codigo"].strip(), nombre_limpio))

		fila = dict(fila)
		fila["nombre_cuenta"] = nombre_limpio
		salida.append(fila)

		for hijo in hijos:
			if hijo["codigo"] in codigos:
				# Ya existía como fila propia: no duplicar, el CSV manda.
				continue
			codigos.add(hijo["codigo"])
			salida.append(hijo)
			recuperadas.append(hijo["codigo"])

	# Validación final: ninguna cuenta recuperada puede quedar colgando de un padre
	# inexistente, y su root_type tiene que coincidir con el de ese padre. Si algo
	# no cuadra, se lanza en vez de importar un plan silenciosamente inconsistente.
	por_codigo = {f["codigo"].strip(): f for f in salida}
	for cod in recuperadas:
		hijo = por_codigo[cod]
		padre = por_codigo.get(hijo["codigo_padre"])
		if not padre:
			raise ReparacionError(
				f"Cuenta recuperada {cod} (hallada en {hijo['_hallada_en']}): "
				f"su padre derivado {hijo['codigo_padre']} no existe en el plan"
			)
		if padre["root_type"] != hijo["root_type"]:
			raise ReparacionError(
				f"Cuenta recuperada {cod}: root_type {hijo['root_type']} no coincide "
				f"con el de su padre {hijo['codigo_padre']} ({padre['root_type']})"
			)

	regrupadas = normalizar_is_group(salida)

	informe = {
		"filas_originales": len(filas),
		"regrupadas": regrupadas,
		"filas_con_nombre_corrupto": len(limpiadas),
		"cuentas_recuperadas": len(recuperadas),
		"codigos_recuperados": recuperadas,
		"nombres_limpiados": limpiadas,
		"filas_resultantes": len(salida),
	}
	return salida, informe
