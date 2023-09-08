# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
import uuid
from frappe import _
from frappe import publish_progress
from frappe.core.api.file import create_new_folder
from frappe.utils.file_manager import save_file
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class Contract(Document):
	# def autoname(self):
	# 	name = self.party_name

	# 	if self.contract_template:
	# 		name += " - {} Agreement".format(self.contract_template)

	# 	# If identical, append contract name with the next number in the iteration
	# 	if frappe.db.exists("Contract", name):
	# 		count = len(frappe.get_all("Contract", filters={"name": ["like", "%{}%".format(name)]}))
	# 		name = "{} - {}".format(name, count)

	# 	self.name = _(name)

	def validate(self):
		self.validate_dates()
		self.update_contract_status()
		self.update_fulfilment_status()

	def before_submit(self):
		self.signed_by_company = frappe.session.user

	def before_update_after_submit(self):
		self.update_contract_status()
		self.update_fulfilment_status()

	def validate_dates(self):
		if self.end_date and self.end_date < self.start_date:
			frappe.throw(_("End Date cannot be before Start Date."))

	def update_contract_status(self):
		if self.is_signed:
			self.status = get_status(self.start_date, self.end_date)
		else:
			self.status = "Unsigned"

	def update_fulfilment_status(self):
		fulfilment_status = "N/A"

		if self.requires_fulfilment:
			fulfilment_progress = self.get_fulfilment_progress()

			if not fulfilment_progress:
				fulfilment_status = "Unfulfilled"
			elif fulfilment_progress < len(self.fulfilment_terms):
				fulfilment_status = "Partially Fulfilled"
			elif fulfilment_progress == len(self.fulfilment_terms):
				fulfilment_status = "Fulfilled"

			if fulfilment_status != "Fulfilled" and self.fulfilment_deadline:
				now_date = getdate(nowdate())
				deadline_date = getdate(self.fulfilment_deadline)

				if now_date > deadline_date:
					fulfilment_status = "Lapsed"

		self.fulfilment_status = fulfilment_status

	def get_fulfilment_progress(self):
		return len([term for term in self.fulfilment_terms if term.fulfilled])
	
	@frappe.whitelist()
	def send_contract(self):
		# Create approval id
		str_uuid = str(uuid.uuid4())
		self.approval_id = str_uuid
		self.save()
		if not self.contact_email and not self.contact_mobile:
			frappe.msgprint(_("Could not find email or mobile phone to send information"))
		else:
			# Send Email
			self.send_contract_email()
			# Send SMS
			self.send_contract_sms()

	@frappe.whitelist()
	def send_contract_email(self):
		# Send Email
		if self.contact_email:
			if not self.approval_id:
				str_uuid = str(uuid.uuid4())
				self.approval_id = str_uuid
				self.save()
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/contract/" + self.approval_id
			push_email = frappe.new_doc('Push Email')
			push_email.to_email = self.contact_email
			push_email.reference_type = "Contract"
			push_email.reference_name = self.name
			push_email.link = approval_url
			push_email.insert(ignore_permissions=True)
			#Check send ok
			last_push = frappe.get_last_doc('Push Email')
			if last_push.send_id:
				# Add comments
				frappe.get_doc({
					'doctype': 'Comment',
					'comment_type': 'Comment',
					'reference_doctype': 'Contract',
					'reference_name': self.name,
					'content': 'Đã gửi email thông báo đến: ' + self.contact_email,
				}).insert(ignore_permissions=True)
				frappe.msgprint('Đã gửi email thông báo đến: ' + self.contact_email)
				# Update comment flag
				if self.comment_flag == 1:
					self.comment_flag = 0
					self.save()
			else:
				frappe.msgprint('Gửi email thất bại.')
		else:
			frappe.msgprint(_("Could not find email to send information"))

	@frappe.whitelist()
	def send_contract_sms(self):
		if	self.contact_mobile:
			if not self.approval_id:
				str_uuid = str(uuid.uuid4())
				self.approval_id = str_uuid
				self.save()
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/contract/" + self.approval_id
			push_sms = frappe.new_doc('Push SMS')
			push_sms.phone_number = self.contact_mobile.replace('0','84', 1).replace(' ','')
			push_sms.reference_type = "Contract"
			push_sms.reference_name = self.name
			push_sms.url = approval_url
			push_sms.insert(ignore_permissions=True)
			#Check send ok
			last_push = frappe.get_last_doc('Push SMS')
			if last_push.result == 1:
				# Add comments
				frappe.get_doc({
					'doctype': 'Comment',
					'comment_type': 'Comment',
					'reference_doctype': 'Contract',
					'reference_name': self.name,
					'content': 'Đã gửi SMS thông báo đến: ' + self.contact_mobile,
				}).insert(ignore_permissions=True)
				frappe.msgprint('Đã gửi SMS thông báo đến: ' + self.contact_mobile)
				# Update comment flag
				if self.comment_flag == 1:
					self.comment_flag = 0
					self.save()
			else:
				frappe.msgprint('Gửi SMS thất bại.')
		else:
			frappe.msgprint(_("Could not find mobile phone to send information"))

	@frappe.whitelist()
	def attach_pdf(doc, event=None):
		template_to_pdf(doc, event=None)


def get_status(start_date, end_date):
	"""
	Get a Contract's status based on the start, current and end dates

	Args:
	        start_date (str): The start date of the contract
	        end_date (str): The end date of the contract

	Returns:
	        str: 'Active' if within range, otherwise 'Inactive'
	"""

	if not end_date:
		return "Active"

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	now_date = getdate(nowdate())

	return "Active" if start_date <= now_date <= end_date else "Inactive"


def update_status_for_contracts():
	"""
	Run the daily hook to update the statuses for all signed
	and submitted Contracts
	"""

	contracts = frappe.get_all(
		"Contract",
		filters={"is_signed": True, "docstatus": 1},
		fields=["name", "start_date", "end_date"],
	)

	for contract in contracts:
		status = get_status(contract.get("start_date"), contract.get("end_date"))

		frappe.db.set_value("Contract", contract.get("name"), "status", status)

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
