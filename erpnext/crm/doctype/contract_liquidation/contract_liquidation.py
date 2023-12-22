# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import uuid
from frappe import _
from frappe import publish_progress
from frappe.core.api.file import create_new_folder
from frappe.utils.file_manager import save_file
from frappe.utils import getdate, nowdate
from frappe.model.document import Document

class ContractLiquidation(Document):
	@frappe.whitelist()
	def attach_pdf(doc, event=None):
		template_to_pdf(doc, event=None)

	@frappe.whitelist()
	def link_contract_data(self):
		ref = frappe.get_doc('Contract',self.contract_number)
		return ref
	
	@frappe.whitelist()
	def update_ref_contract(self):
		ref = frappe.get_doc('Contract',self.contract_number)
		if not ref.contract_liquidation:
			ref.contract_liquidation = self.name
			ref.save(ignore_permissions=True)
	pass
def template_to_pdf (doc, event=None):

	progress = frappe._dict(title=_("Creating PDF ..."), percent=0, doctype=doc.doctype, docname=doc.name)
	publish_progress(**progress)

	html = frappe.get_print(doc.doctype, doc.name, doc.print_template, letterhead=None)

	progress.percent = 33
	publish_progress(**progress)

	pdf_data = frappe.utils.pdf.get_pdf(html)

	progress.percent = 66
	publish_progress(**progress)

	file_name = doc.name.replace("/","-") + "-.pdf"
	save_file(file_name, pdf_data, doc.doctype, doc.name, folder= "Home", is_private = 1, df = "unsigned_file")
	attach_file = frappe.get_last_doc("File")
	
	progress.percent = 100
	publish_progress(**progress)

	doc.unsigned_file = attach_file.file_url
	doc.save()