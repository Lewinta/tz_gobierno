// Copyright (c) 2026, TZCode S.R.L. and contributors
// For license information, please see license.txt

frappe.query_reports["Estado de Cambios en Patrimonio DIGECOG"] = {
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
			fieldname: "fiscal_year",
			label: __("Año Fiscal"),
			fieldtype: "Link",
			options: "Fiscal Year",
			reqd: 1,
			default: frappe.defaults.get_user_default("fiscal_year"),
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
