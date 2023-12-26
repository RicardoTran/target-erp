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
	def get_quotation_doc(self):
		refContract = frappe.get_doc('Contract',self.contract_number)
		ref = frappe.get_doc('Quotation',refContract.document_name)
		return ref
	
	@frappe.whitelist()
	def get_customer_doc(self):
		refContract = frappe.get_doc('Contract',self.contract_number)
		ref = frappe.get_doc('Customer',refContract.party_name)
		return ref
	
	@frappe.whitelist()
	def get_email_global(self):
		g_email = frappe.db.get_single_value("Push Email Settings","global_email")
		return g_email
	
	@frappe.whitelist()
	def get_territory_doc(self):
		refContract = frappe.get_doc('Contract',self.contract_number)
		refCustomer = frappe.get_doc('Customer',refContract.party_name)
		ref = frappe.get_doc('Territory',refCustomer.territory)
		return ref

	@frappe.whitelist()
	def update_ref_contract(self):
		ref = frappe.get_doc('Contract',self.contract_number)
		if not ref.contract_liquidation:
			ref.contract_liquidation = self.name
			ref.save(ignore_permissions=True)
	
	@frappe.whitelist()
	def send_contract_liquidation(self):
		# Create approval id
		str_uuid = str(uuid.uuid4())
		self.approval_id = str_uuid
		self.save()
		if (not self.contact_email and not self.cc_email):
			frappe.msgprint(_("Could not find email to send information"))
		else:
			# Send Email
			self.send_contract_liquidation_email()

		if	(not self.contact_mobile and not self.cc_mobile):
			frappe.msgprint(_("Could not find mobile phone to send information"))
		else:
			#Send sms
			self.send_contract_liquidation_sms()

		# if not self.contact_email and not self.contact_mobile:
		# 	frappe.msgprint(_("Could not find email or mobile phone to send information"))
		# else:
		# 	# Send Email
		# 	self.send_contract_liquidation_email()
		# 	# Send SMS
		# 	self.send_contract_liquidation_sms()

	@frappe.whitelist()
	def send_contract_liquidation_email(self):
		# Send Email
		if (not self.contact_email and not self.cc_email):
			frappe.msgprint(_("Could not find email to send information"))
		else:
			list_email = self.contact_email + "," + self.cc_email
			list_email = list_email.lstrip(',').rstrip(',')
			if not self.approval_id:
				str_uuid = str(uuid.uuid4())
				self.approval_id = str_uuid
				self.save()
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/contract_liquidation/" + self.approval_id  

			#Get template
			template = frappe.db.get_value('Push Email Template', {'reference_type':'Contract Liquidation','template':'MAU-001'}, ['subject','body'], as_dict=1)
			body = template.body.replace('{{link}}', approval_url)
			body = body.replace('{{link_name}}', self.name)

			#customer
			refCongty = frappe.get_doc('Customer', self.customer)
			body = body.replace('{{company_name}}', refCongty.company_name)


			#Quotation
			refContract = frappe.get_doc('Contract',self.contract_number)
			refQuote = frappe.get_doc('Quotation',refContract.document_name)
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
				body = body.replace('{{email}}', 'Email: ' + refSign.email)

			if not refSign.mobile:
				body = body.replace('{{mobile}}', '')
			else:
				body = body.replace('{{mobile}}', 'Mobiphone: ' + refSign.mobile)

			push_email = frappe.new_doc('Push Email')
			push_email.to_email = list_email
			push_email.reply_to = self.cc_email
			push_email.subject = template.subject
			push_email.body = body
			push_email.reference_type = "Contract Liquidation"
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
					'reference_doctype': 'Contract Liquidation',
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
	def send_contract_liquidation_sms(self):
		if	(not self.contact_mobile and not self.cc_mobile):
			frappe.msgprint(_("Could not find mobile phone to send information"))
		else:
			list_mobile = self.contact_mobile + "," + self.cc_mobile
			list_mobile = list_mobile.lstrip(',').rstrip(',')
			arr_mobile = list_mobile.split(",")
			if not self.approval_id:
				str_uuid = str(uuid.uuid4())
				self.approval_id = str_uuid
				self.save()
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/contract_liquidation/" + self.approval_id

			#Get template
			template = frappe.db.get_value('Push SMS Template', {'reference_type':'Contract Liquidation','template':'MAU-001'}, ['body'], as_dict=1)
			body = template.body.replace('{{link}}', approval_url)
			body = body.replace('{{link_name}}', self.name)

			#customer
			refCongty = frappe.get_doc('Customer', self.customer)
			body = body.replace('{{company_name}}', refCongty.company_name)


			#Quotation
			refContract = frappe.get_doc('Contract',self.contract_number)
			refQuote = frappe.get_doc('Quotation',refContract.document_name)
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
				push_sms.unicode_char = 0
				push_sms.reference_type = "Contract Liquidation"
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
						'reference_doctype': 'Contract Liquidation',
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