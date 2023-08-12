# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe import _, msgprint, qb
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password

class PushSMS(Document):
	def after_insert(self):
		self.send_sms_branchname()

	@frappe.whitelist()
	def send_sms_branchname(self):
		#Get login
		login_user = frappe.db.get_single_value("Push SMS Settings","user_name")
		login_pass = get_decrypted_password("Push SMS Settings","Push SMS Settings","password")
		service_id = frappe.db.get_single_value("Push SMS Settings","service_id")

		#Get template
		template = frappe.db.get_value('Push SMS Template', {'reference_type':self.reference_type}, ['content'], as_dict=1)
		content = template.content.replace('{{link}}', self.url)

		#Send SMS
		url = "https://ams.tinnhanthuonghieu.vn:8998/bulkapi?wsdl"
		payload = "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:impl=\"http://impl.bulkSms.ws/\">\n   <soapenv:Header/>\n   <soapenv:Body>\n      <impl:wsCpMt>\n         <!--Optional:-->\n         <User>" + login_user + "</User>\n         <!--Optional:-->\n         <Password>" + login_pass + "</Password>\n         <!--Optional:-->\n         <CPCode>" + service_id + "</CPCode>\n         <!--Optional:-->\n         <RequestID>1</RequestID>\n         <!--Optional:-->\n         <UserID>" + self.phone_number + "</UserID>\n         <!--Optional:-->\n         <ReceiverID>" + self.phone_number + "</ReceiverID>\n         <!--Optional:-->\n         <ServiceID>" + service_id + "</ServiceID>\n         <!--Optional:-->\n         <CommandCode>bulksms</CommandCode>\n         <!--Optional:-->\n         <Content>" + content + "</Content>\n         <!--Optional:-->\n         <ContentType>" + str(self.unicode_char) + "</ContentType>\n      </impl:wsCpMt>\n   </soapenv:Body>\n</soapenv:Envelope>\n"
		headers = {
			'Content-Type': 'text/xml'
		}
		response = requests.request("POST", url, headers=headers, data=payload)
		frappe.get_doc({
			'doctype': 'Comment',
			'comment_type': 'Comment',
			'reference_doctype': 'Push SMS',
			'reference_name': self.name,
			'content': response.text,
		}).insert()

		self.content = content
		self.save()
		self.submit()
