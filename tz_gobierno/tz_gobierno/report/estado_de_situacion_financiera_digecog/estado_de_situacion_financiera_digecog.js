// Copyright (c) 2026, TZCode S.R.L. and contributors
// For license information, please see license.txt

frappe.query_reports["Estado de Situacion Financiera DIGECOG"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Institución"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "as_on_date",
			label: __("Al"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "mostrar_periodo_anterior",
			label: __("Comparar con el período anterior"),
			fieldtype: "Check",
			default: 1,
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.es_total) {
			value = `<b>${value}</b>`;
		}
		return value;
	},
};
