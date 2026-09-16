// Copyright (c) 2026, TZCode S.R.L. and contributors
// For license information, please see license.txt

frappe.query_reports["Estado de Flujo de Efectivo DIGECOG"] = {
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
			fieldname: "from_date",
			label: __("Desde"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.year_start(),
		},
		{
			fieldname: "to_date",
			label: __("Hasta"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
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
