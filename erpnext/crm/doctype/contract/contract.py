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
		self.set_party_name_ref()

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
		if (not self.contact_email and not self.cc_email):
			frappe.msgprint(_("Could not find email to send information"))
		else:
			# Send Email
			self.send_contract_email()

		if	(not self.contact_mobile and not self.cc_mobile):
			frappe.msgprint(_("Could not find mobile phone to send information"))
		else:
			#Send sms
			self.send_contract_sms()
		# if not self.contact_email and not self.contact_mobile:
		# 	frappe.msgprint(_("Could not find email or mobile phone to send information"))
		# else:
		# 	# Send Email
		# 	self.send_contract_email()
		# 	# Send SMS
		# 	self.send_contract_sms()

	@frappe.whitelist()
	def send_contract_email(self):
		# Send Email
		if (not self.contact_email and not self.cc_email):
			frappe.msgprint(_("Could not find email to send information"))
		else:
			list_email = (self.contact_email or '') + "," + (self.cc_email or '')
			list_email = list_email.lstrip(',').rstrip(',')
			if not self.approval_id:
				str_uuid = str(uuid.uuid4())
				self.approval_id = str_uuid
				self.save()
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/contract/" + self.approval_id  

			#Get template
			template = frappe.db.get_value('Push Email Template', {'reference_type':'Contract','template':'MAU-001'}, ['subject','body'], as_dict=1)
			body = template.body.replace('{{link}}', approval_url)
			body = body.replace('{{link_name}}', self.name)

			#customer
			refCongty = frappe.get_doc('Customer', self.party_name)
			body = body.replace('{{company_name}}', refCongty.company_name)


			#Quotation
			refQuote = frappe.get_doc('Quotation', self.document_name)
			body = body.replace('{{task_name}}', refQuote.task_description)
			body = body.replace('{{yyyy}}', refQuote.items[0].year_text)

			#sign
			refSign = frappe.get_doc('Territory', refCongty.territory)
			if not refSign.full_name:
				body = body.replace('{{full_name}}', '')
			else:
				body = body.replace('{{full_name}}', refSign.full_name)

			if not refSign.position:
				body = body.replace('{{position}}', '')
			else:
				body = body.replace('{{position}}', refSign.position)

			if not refSign.email:
				body = body.replace('{{email}}', '')
			else:
				body = body.replace('{{email}}', refSign.email)

			if not refSign.mobile:
				body = body.replace('{{mobile}}', '')
			else:
				body = body.replace('{{mobile}}', refSign.mobile)

			push_email = frappe.new_doc('Push Email')
			push_email.to_email = list_email
			push_email.reply_to = self.cc_email
			push_email.subject = template.subject
			push_email.body = body
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
					'content': 'Đã gửi email thông báo đến: ' + list_email,
				}).insert(ignore_permissions=True)
				frappe.msgprint('Đã gửi email thông báo đến: ' + list_email)
				# Update comment flag
				if self.comment_flag == 1:
					self.comment_flag = 0
					self.save()
			else:
				frappe.msgprint('Gửi email đến: ' + list_email + ' thất bại.')

	@frappe.whitelist()
	def send_contract_sms(self):
		if	(not self.contact_mobile and not self.cc_mobile):
			frappe.msgprint(_("Could not find mobile phone to send information"))
		else:
			list_mobile = (self.contact_mobile or '') + "," + (self.cc_mobile or '')
			list_mobile = list_mobile.lstrip(',').rstrip(',')
			arr_mobile = list_mobile.split(",")
			if not self.approval_id:
				str_uuid = str(uuid.uuid4())
				self.approval_id = str_uuid
				self.save()
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/contract/" + self.approval_id

			#Get template
			template = frappe.db.get_value('Push SMS Template', {'reference_type':'Contract','template':'MAU-001'}, ['body'], as_dict=1)
			body = template.body.replace('{{link}}', approval_url)
			body = body.replace('{{link_name}}', self.name)

			#customer
			refCongty = frappe.get_doc('Customer', self.party_name)
			body = body.replace('{{company_name}}', refCongty.company_name)


			#Quotation
			refQuote = frappe.get_doc('Quotation', self.document_name)
			body = body.replace('{{task_name}}', refQuote.task_description)
			body = body.replace('{{yyyy}}', refQuote.items[0].year_text)

			#sign
			refSign = frappe.get_doc('Territory', refCongty.territory)
			if not refSign.full_name:
				body = body.replace('{{full_name}}', '')
			else:
				body = body.replace('{{full_name}}', refSign.full_name)

			if not refSign.position:
				body = body.replace('{{position}}', '')
			else:
				body = body.replace('{{position}}', refSign.position)

			if not refSign.email:
				body = body.replace('{{email}}', '')
			else:
				body = body.replace('{{email}}', refSign.email)

			if not refSign.mobile:
				body = body.replace('{{mobile}}', '')
			else:
				body = body.replace('{{mobile}}', refSign.mobile)

			for x in arr_mobile:
				push_sms = frappe.new_doc('Push SMS')
				push_sms.phone_number = x.replace('0','84', 1).replace(' ','')
				push_sms.body = body
				push_sms.unicode_char = 1
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
						'content': 'Đã gửi SMS thông báo đến: ' + x,
					}).insert(ignore_permissions=True)
					frappe.msgprint('Đã gửi SMS thông báo đến: ' + x)
					# Update comment flag
					if self.comment_flag == 1:
						self.comment_flag = 0
						self.save()
				else:
					frappe.msgprint('Gửi SMS đến số: ' + x + ' thất bại.')

	@frappe.whitelist()
	def attach_pdf(doc, event=None):
		template_to_pdf(doc, event=None)

	@frappe.whitelist()
	def link_quotation_data(self):
		ref = frappe.get_doc('Quotation',self.document_name)
		return ref
	
	@frappe.whitelist()
	def get_customer_doc(self):
		refQuotation = frappe.get_doc('Quotation',self.document_name)
		ref = frappe.get_doc('Customer',refQuotation.party_name)
		return ref

	@frappe.whitelist()
	def get_email_global(self):
		g_email = frappe.db.get_single_value("Push Email Settings","global_email")
		return g_email
	
	@frappe.whitelist()
	def get_territory_doc(self):
		refQuotation = frappe.get_doc('Quotation',self.document_name)
		refCustomer = frappe.get_doc('Customer',refQuotation.party_name)
		ref = frappe.get_doc("Territory",refCustomer.territory)
		return ref
	
	@frappe.whitelist()
	def update_ref_quotation(self):
		ref = frappe.get_doc('Quotation',self.document_name)
		if not ref.contract:
			ref.contract = self.name
			ref.save(ignore_permissions=True)

	def set_party_name_ref(self):
		if self.party_name and self.party_type == "Customer":
			self.party_name_ref = frappe.db.get_value("Customer", self.party_name, "customer_name")
		if self.party_name and self.party_type == "Supplier":
			self.party_name_ref = frappe.db.get_value("Supplier", self.party_name, "supplier_name")
		if self.party_name and self.party_type == "Employee":
			f_name, l_name = frappe.db.get_value("Employee", self.party_name, ["first_name","last_name"])
			self.party_name_ref = f_name + ' ' + l_name
	

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

	strAdd = frappe.db.get_value("Customer", doc.party_name, "customer_name")

	file_name = doc.name.replace("/","-") + "-" + strAdd.replace(" ","-") + "-.pdf"
	save_file(file_name, pdf_data, doc.doctype, doc.name, folder= "Home", is_private = 1, df = "unsigned_file")
	attach_file = frappe.get_last_doc("File")
	
	progress.percent = 100
	publish_progress(**progress)

	doc.unsigned_file = attach_file.file_url
	doc.save()
