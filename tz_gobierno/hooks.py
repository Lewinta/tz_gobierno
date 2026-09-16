app_name = "tz_gobierno"
app_title = "TZ Gobierno"
app_publisher = "TZCode S.R.L."
app_description = "Contabilidad gubernamental dominicana (DIGECOG) para ERPNext"
app_email = "lewin.villar@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tz_gobierno",
# 		"logo": "/assets/tz_gobierno/logo.png",
# 		"title": "TZ Gobierno",
# 		"route": "/tz_gobierno",
# 		"has_permission": "tz_gobierno.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/tz_gobierno/css/tz_gobierno.css"
# app_include_js = "/assets/tz_gobierno/js/tz_gobierno.js"

# include js, css files in header of web template
# web_include_css = "/assets/tz_gobierno/css/tz_gobierno.css"
# web_include_js = "/assets/tz_gobierno/js/tz_gobierno.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tz_gobierno/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tz_gobierno/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "tz_gobierno.utils.jinja_methods",
# 	"filters": "tz_gobierno.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tz_gobierno.install.before_install"
# after_install = "tz_gobierno.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "tz_gobierno.uninstall.before_uninstall"
# after_uninstall = "tz_gobierno.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tz_gobierno.utils.before_app_install"
# after_app_install = "tz_gobierno.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tz_gobierno.utils.before_app_uninstall"
# after_app_uninstall = "tz_gobierno.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "tz_gobierno.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tz_gobierno.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"tz_gobierno.tasks.all"
# 	],
# 	"daily": [
# 		"tz_gobierno.tasks.daily"
# 	],
# 	"hourly": [
# 		"tz_gobierno.tasks.hourly"
# 	],
# 	"weekly": [
# 		"tz_gobierno.tasks.weekly"
# 	],
# 	"monthly": [
# 		"tz_gobierno.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "tz_gobierno.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "tz_gobierno.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "tz_gobierno.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tz_gobierno.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tz_gobierno.utils.before_request"]
# after_request = ["tz_gobierno.utils.after_request"]

# Job Events
# ----------
# before_job = ["tz_gobierno.utils.before_job"]
# after_job = ["tz_gobierno.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"tz_gobierno.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Subledger presupuestario (§4 del spec CES-0009): el ciclo compromiso → devengado
# → pagado se engancha al flujo estándar de compras de ERPNext, para que el usuario
# no tenga que registrar nada aparte.
doc_events = {
	"Purchase Order": {
		"before_submit": "tz_gobierno.presupuesto.validar_disponibilidad",
		"on_submit": "tz_gobierno.presupuesto.registrar_compromiso",
		"on_cancel": "tz_gobierno.presupuesto.revertir_compromiso",
	},
	"Purchase Invoice": {
		"on_submit": "tz_gobierno.presupuesto.registrar_devengado",
		"on_cancel": "tz_gobierno.presupuesto.revertir_devengado",
	},
	"Payment Entry": {
		"on_submit": "tz_gobierno.presupuesto.registrar_pagado",
		"on_cancel": "tz_gobierno.presupuesto.revertir_pagado",
	},
}
