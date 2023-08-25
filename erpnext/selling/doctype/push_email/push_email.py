# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import requests
import json
from frappe import _, msgprint, qb
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password

class PushEmail(Document):
	def after_insert(self):
		self.send_email_notify()

	@frappe.whitelist()
	def send_email_notify(self):
		#Get login
		api_key = get_decrypted_password("Push Email Settings","Push Email Settings","api_key")
		api_key = "Bearer " + api_key
		from_email = frappe.db.get_single_value("Push Email Settings","from_email")

		#Get template
		template = frappe.db.get_value('Push Email Template', {'reference_type':self.reference_type}, ['subject','body'], as_dict=1)
		body = template.body.replace('{{link}}', self.link)
		body = body.replace('{{link_name}}', self.reference_name)
		to_email = self.to_email.replace(" ", "").strip().split(",")

		#Send email
		url = "https://api.resend.com/emails"

		payload = json.dumps({
		"from": from_email,
		"to": to_email,
		"subject": template.subject,
		"html": body
		})
		headers = {
		'Content-Type': 'application/json',
		'Authorization': api_key
		}

		response = requests.request("POST", url, headers=headers, data=payload)
		jsonstr = json.loads(response.text)
		
		frappe.get_doc({
			'doctype': 'Comment',
			'comment_type': 'Comment',
			'reference_doctype': 'Push Email',
			'reference_name': self.name,
			'content': response.text,
		}).insert(ignore_permissions=True)

		#Update
		self.from_email = from_email
		self.subject = template.subject
		self.body = body
		if 'id' in response.text:
			self.send_id = jsonstr["id"]
		self.save(ignore_permissions=True)
		# self.submit()
