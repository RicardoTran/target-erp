# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
import frappe.defaults
from frappe import _, msgprint, qb
from frappe.model.document import Document

class CustomerUser(Document):
	def validate(self):
		if not frappe.db.exists("User", self.email):
			frappe.get_doc(dict(
            doctype = "User",
            first_name = self.full_name,
            email = self.email,
            user_type = "Website User",
            send_welcome_email = 0,
            language = "vi",
            time_zone = "Asia/Ho_Chi_Minh",
            enabled = self.enabled
        )).insert(ignore_permissions=True)
		else:
			check = frappe.db.get_value('User', self.email, ['user_type'],as_dict=1)
			if "System" in check.user_type:
				frappe.throw(_('Email already exists on the system, please check again!'))
			else:
				update_user = frappe.get_doc("User",self.email)
				update_user.first_name = self.full_name
				update_user.enabled = self.enabled
				update_user.save(ignore_permissions=True)

	def on_trash(self):
		if not frappe.db.exists("User", self.email):
			check = frappe.db.get_value('User', self.email, ['user_type'],as_dict=1)
			if "Website" in check.user_type:
				ref_user = frappe.get_doc("User",self.email)
				ref_user.delete(ignore_permissions=True)

