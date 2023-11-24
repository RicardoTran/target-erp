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
		body = remove_accents(self.body)

		#Send SMS
		url = "https://ams.tinnhanthuonghieu.vn:8998/bulkapi?wsdl"
		payload = "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:impl=\"http://impl.bulkSms.ws/\">\n   <soapenv:Header/>\n   <soapenv:Body>\n      <impl:wsCpMt>\n         <!--Optional:-->\n         <User>" + login_user + "</User>\n         <!--Optional:-->\n         <Password>" + login_pass + "</Password>\n         <!--Optional:-->\n         <CPCode>" + service_id + "</CPCode>\n         <!--Optional:-->\n         <RequestID>1</RequestID>\n         <!--Optional:-->\n         <UserID>" + self.phone_number + "</UserID>\n         <!--Optional:-->\n         <ReceiverID>" + self.phone_number + "</ReceiverID>\n         <!--Optional:-->\n         <ServiceID>" + service_id + "</ServiceID>\n         <!--Optional:-->\n         <CommandCode>bulksms</CommandCode>\n         <!--Optional:-->\n         <Content>" + body + "</Content>\n         <!--Optional:-->\n         <ContentType>" + str(self.unicode_char) + "</ContentType>\n      </impl:wsCpMt>\n   </soapenv:Body>\n</soapenv:Envelope>\n"
		headers = {
			'Content-Type': 'text/xml'
		}
		response = requests.request("POST", url, headers=headers, data=payload, )

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