# tz_gobierno

App de Frappe/ERPNext para contabilidad gubernamental dominicana (normativa DIGECOG).

Construida por **TZCode S.R.L.** para la licitación **CES-DAF-CM-2026-0009** (Consejo
Económico y Social), pero deliberadamente genérica: no hay nada hardcodeado del CES
salvo donde el pliego lo exige, para poder reusarla en las demás licitaciones del
Estado dominicano.

Sitio de desarrollo/demo: `gob.tzcode.net`.

---

## ⚠️ Hallazgo crítico sobre el plan de cuentas — leer antes de la demo

El spec `CES-0009_spec-implementacion-erpnext.md` afirma que `plan_de_cuentas_digecog.csv`
contiene las 3,595 cuentas del plan y que su único problema de integridad es la cuenta
huérfana `4.9.99`.

**Eso no es exacto.** Al importar se detectó un segundo defecto, mayor:

| | |
|---|---|
| Filas en el CSV | 3,595 |
| Filas con `nombre_cuenta` corrupto | **40** (23 de nivel 6, 17 de nivel 7) |
| Cuentas de nivel 7 ausentes del CSV | **80** |
| Cuentas reales del plan | **3,675** |

La extracción del PDF a CSV concatenó, dentro de la celda `nombre_cuenta` de esas 40
filas, las filas que les seguían en la tabla del documento. Ejemplo real:

```
codigo        : 1.1.05.07.01.02
nombre_cuenta : "Textiles y vestuarios venta o cesión
                 1.1.05.07.01.02.01 Textiles y vestuarios venta o cesión S
                 1.1.05.07.01.02.99 Textiles y vestuarios venta o cesión - Pérdidas por deterioro S"
```

De los 80 códigos embebidos, 51 son hijos de la fila contenedora y 29 son hermanos
(son simplemente "la fila siguiente"), así que el padre de cada cuenta recuperada se
deriva de su propio código, no de dónde apareció.

`tz_gobierno/digecog/reparacion_csv.py` recupera las 80 cuentas y limpia los 40
nombres, con un parser **estricto**: si encuentra una forma que no reconoce, lanza en
vez de adivinar. Valida además que cada cuenta recuperada tenga padre existente y
`root_type` coherente con ese padre.

**Pendiente antes de la demo:** esto es un rescate de texto ya degradado, no una
re-extracción del PDF oficial (que no está en el bench). Hay que **validar las 80
cuentas recuperadas contra el PDF oficial de DIGECOG**. Listado:

```bash
bench --site gob.tzcode.net execute tz_gobierno.digecog.verificacion.imprimir_resumen \
  --kwargs "{'company':'CES - Consejo Económico y Social'}"
```

Dado que la cláusula 16.1.1 del pliego es excluyente, importar un plan al que le
faltan 80 cuentas obligatorias sería precisamente el tipo de no conformidad que
descalifica la oferta. Por eso no se dejó pasar.

### Segundo defecto: 18 cuentas "ledger con hijos"

Independiente del anterior y **también presente en el CSV crudo**: 18 cuentas vienen
marcadas `imputable=S` / `is_group=0` pero tienen hijos en el plan. ERPNext no puede
modelar eso — `Account.validate_parent()` lanza *"Parent account can not be a ledger"*.

`normalizar_is_group()` hace que la jerarquía mande sobre el flag: si una cuenta tiene
hijos, es grupo. No se pierde capacidad de registro, porque la regla de DIGECOG es
imputar siempre al nivel más bajo, que son justamente los hijos de esas 18.

### Nombres truncados

`tabAccount.name` es `varchar(140)` y Frappe lo arma como
`{account_number} - {account_name} - {abbr}`. Siete cuentas tienen nombres oficiales
que no caben. En esos casos `account_name` se trunca con `…` y el nombre oficial
íntegro queda en el custom field `nombre_digecog_completo` — no se pierde nada.

---

## Estado de implementación

| Sección del spec | Módulo | Estado |
|---|---|---|
| §3 Plan de cuentas DIGECOG | `digecog/coa_import.py` | Completo, 9 tests |
| §4 Subledger presupuestario | `presupuesto.py` + doctypes `Linea/Movimiento Presupuestario` | Completo, 12 tests |
| §5 Estados Financieros (5) | `digecog/estados.py` + 5 Script Reports | Completo, 21 tests |
| §7 Módulos secundarios | `nomina.py`, `encuestas.py`, `activos.py`, `rnc.py` | Completo, 29 tests |
| §5.6 Notas a los EEFF | doctype + reporte que avisa cuáles faltan | Completo |
| §8 Módulos parametrizables | `nomina_bancaria.py`, `Importacion SIAB`, `Solicitud Tramite Pago` | Completo, 19 tests |

## Instalación

```bash
bench get-app git@github.com:Lewinta/tz_gobierno.git
bench --site <sitio> install-app tz_gobierno
```

Requiere `erpnext` y `hrms` instalados en el sitio.

### Sembrar el plan de cuentas

```bash
# Company sin el plan de cuentas por defecto de ERPNext
bench --site <sitio> execute tz_gobierno.digecog.coa_import.crear_company_sin_coa_estandar \
  --kwargs "{'nombre':'CES - Consejo Económico y Social','abbr':'CES'}"

# Import del plan DIGECOG (idempotente)
bench --site <sitio> execute tz_gobierno.digecog.coa_import.ejecutar \
  --kwargs "{'company':'CES - Consejo Económico y Social'}"
```

> **Nota sobre `bench execute`:** en Frappe v16 `bench execute` llama a la función
> dentro de un `try` y, ante *cualquier* excepción, cae a un `eval` que falla con
> `NameError: name 'tz_gobierno' is not defined`. Ese mensaje **oculta el error real**.
> Para depurar, invocar la función desde un script propio con `frappe.init()`.

## Tests

```bash
bench --site gob.tzcode.net run-tests --app tz_gobierno
```

## Convenciones

Los nombres de DocType van **sin tilde** (`Linea Presupuestaria`, no `Línea`) porque
`frappe.scrub()` los convierte en nombres de módulo Python y de carpeta, y una tilde
produce un identificador no-ASCII. El label con tilde se resuelve por traducción.


---

## Pendientes reales, por orden de importancia

1. **Validar las 80 cuentas recuperadas contra el PDF oficial de DIGECOG.** Es el
   único punto donde el sistema se apoya en un rescate de texto degradado y no en la
   fuente oficial. Con la cláusula 16.1.1 de por medio, conviene cerrarlo antes de la
   demo.
2. **Confirmar el mapeo cuenta→rubro de los Estados Financieros** con quien conozca
   los modelos de DIGECOG. La cobertura es total (ninguna cuenta queda fuera) y los
   estados cuadran, pero que una cuenta caiga en el rubro *correcto* es un juicio
   normativo que el código no puede verificar solo. Todo el mapeo está en un único
   archivo, `digecog/mapeo.py`, precisamente para que revisarlo sea leer una tabla.
3. **Clasificador presupuestario oficial** para el Estado 5.5: hoy el objeto del gasto
   se aproxima por los grupos del plan DIGECOG. Marcado con `TODO` en `mapeo.py`.
4. **Layout de Banreservas y formulario del CES**: los módulos ya son
   parametrizables; cuando lleguen los documentos es editar registros, no programar.
5. **Cédula del empleado**: `nomina_bancaria._cedula_de()` busca en varios campos
   posibles porque ERPNext no tiene uno estándar. Conviene fijar un custom field.

## Lo que este app decide distinto al spec, y por qué

| Punto | Spec | Aquí | Motivo |
|---|---|---|---|
| Total de cuentas | 3,595 | 3,675 | El CSV perdió 80 cuentas por la extracción del PDF |
| `disponible` | `modificado − comprometido` | `− comprometido − devengado − pagado` | Con la fórmula del spec, facturar una orden devolvía el presupuesto como si nada se hubiera gastado |
| Reversos | etapa `Reversado` | igual, más `etapa_revertida` y `disparador_*` | Sin saber qué etapa anula un reverso y quién lo disparó, los saldos se iban a negativo |
| Nombre del app | `tzcode_gov` | `tz_gobierno` | Coincide con el repo y con la convención `tz_*` |
| Nombres de DocType | con tilde | sin tilde | `frappe.scrub()` los vuelve nombres de módulo Python |
