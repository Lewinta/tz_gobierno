// Copyright (c) 2026, TZCode S.R.L. and contributors
// For license information, please see license.txt

frappe.query_reports["Notas a los Estados Financieros DIGECOG"] = {
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
};
