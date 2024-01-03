# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import json
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
		# body = remove_accents(self.body)
		body = self.body
		unicode = str(self.unicode_char)
		#Send SMS
		url = "https://ams.tinnhanthuonghieu.vn:8998/bulkapi?wsdl"
		payload = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:impl="http://impl.bulkSms.ws/"><soapenv:Header/><soapenv:Body><impl:wsCpMt><User>'+login_user+'</User><Password>'+login_pass+'</Password><CPCode>'+service_id+'</CPCode><RequestID>1</RequestID><UserID>'+self.phone_number+'</UserID><ReceiverID>'+self.phone_number+'</ReceiverID><ServiceID>'+service_id+'</ServiceID><CommandCode>bulksms</CommandCode><Content>'+body+'</Content><ContentType>'+unicode+'</ContentType></impl:wsCpMt></soapenv:Body></soapenv:Envelope>'
		headers = {
			'Content-Type': 'text/xml; charset=utf-8'
		}
		response = requests.request("POST", url, headers=headers, data=payload.encode('utf-8'), )

		frappe.get_doc({
			'doctype': 'Comment',
			'comment_type': 'Comment',
			'reference_doctype': 'Push SMS',
			'reference_name': self.name,
			'content': response.text,
		}).insert(ignore_permissions=True)
		if '<result>1</result>' in response.text:
			self.result = 1
		else:
			self.result = 0
		self.save(ignore_permissions=True)
		# self.submit()

def remove_accents(input_str):
	s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
	s0 = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
	s = ''
	input_str.encode('utf-8')
	for c in input_str:
		if c in s1:
			s += s0[s1.index(c)]
		else:
			s += c
	return s