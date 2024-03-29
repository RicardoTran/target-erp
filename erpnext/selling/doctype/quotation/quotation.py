# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
import uuid
import json
from datetime import date
from num2words import num2words
from frappe import _
from frappe import publish_progress
from frappe.core.api.file import create_new_folder
from frappe.utils.file_manager import save_file
from frappe.utils.weasyprint import PrintFormatGenerator
from frappe.model.naming import _format_autoname
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate, nowdate
from datetime import datetime

from erpnext.controllers.selling_controller import SellingController

form_grid_templates = {"items": "templates/form_grid/item_grid.html"}


class Quotation(SellingController):
	def set_indicator(self):
		if self.docstatus == 1:
			self.indicator_color = "blue"
			self.indicator_title = "Submitted"
		if self.valid_till and getdate(self.valid_till) < getdate(nowdate()):
			self.indicator_color = "gray"
			self.indicator_title = "Expired"

	def validate(self):
		super(Quotation, self).validate()
		self.set_status()
		self.validate_uom_is_integer("stock_uom", "qty")
		self.validate_valid_till()
		self.validate_shopping_cart_items()
		self.set_customer_name()
		if self.items:
			self.with_items = 1

		from erpnext.stock.doctype.packed_item.packed_item import make_packing_list

		make_packing_list(self)

	def before_submit(self):
		self.set_has_alternative_item()

	def validate_valid_till(self):
		if self.valid_till and getdate(self.valid_till) < getdate(self.transaction_date):
			frappe.throw(_("Valid till date cannot be before transaction date"))

	def validate_shopping_cart_items(self):
		if self.order_type != "Shopping Cart":
			return

		for item in self.items:
			has_web_item = frappe.db.exists("Website Item", {"item_code": item.item_code})

			# If variant is unpublished but template is published: valid
			template = frappe.get_cached_value("Item", item.item_code, "variant_of")
			if template and not has_web_item:
				has_web_item = frappe.db.exists("Website Item", {"item_code": template})

			if not has_web_item:
				frappe.throw(
					_("Row #{0}: Item {1} must have a Website Item for Shopping Cart Quotations").format(
						item.idx, frappe.bold(item.item_code)
					),
					title=_("Unpublished Item"),
				)

	def set_has_alternative_item(self):
		"""Mark 'Has Alternative Item' for rows."""
		if not any(row.is_alternative for row in self.get("items")):
			return

		items_with_alternatives = self.get_rows_with_alternatives()
		for row in self.get("items"):
			if not row.is_alternative and row.name in items_with_alternatives:
				row.has_alternative_item = 1

	def get_ordered_status(self):
		status = "Open"
		ordered_items = frappe._dict(
			frappe.db.get_all(
				"Sales Order Item",
				{"prevdoc_docname": self.name, "docstatus": 1},
				["item_code", "sum(qty)"],
				group_by="item_code",
				as_list=1,
			)
		)

		if not ordered_items:
			return status

		has_alternatives = any(row.is_alternative for row in self.get("items"))
		self._items = self.get_valid_items() if has_alternatives else self.get("items")

		if any(row.qty > ordered_items.get(row.item_code, 0.0) for row in self._items):
			status = "Partially Ordered"
		else:
			status = "Ordered"

		return status

	def get_valid_items(self):
		"""
		Filters out items in an alternatives set that were not ordered.
		"""

		def is_in_sales_order(row):
			in_sales_order = bool(
				frappe.db.exists(
					"Sales Order Item", {"quotation_item": row.name, "item_code": row.item_code, "docstatus": 1}
				)
			)
			return in_sales_order

		def can_map(row) -> bool:
			if row.is_alternative or row.has_alternative_item:
				return is_in_sales_order(row)

			return True

		return list(filter(can_map, self.get("items")))

	def is_fully_ordered(self):
		return self.get_ordered_status() == "Ordered"

	def is_partially_ordered(self):
		return self.get_ordered_status() == "Partially Ordered"

	def update_lead(self):
		if self.quotation_to == "Lead" and self.party_name:
			frappe.get_doc("Lead", self.party_name).set_status(update=True)

	def set_customer_name(self):
		if self.party_name and self.quotation_to == "Customer":
			self.customer_name = frappe.db.get_value("Customer", self.party_name, "customer_name")
		elif self.party_name and self.quotation_to == "Lead":
			lead_name, company_name = frappe.db.get_value(
				"Lead", self.party_name, ["lead_name", "company_name"]
			)
			self.customer_name = company_name or lead_name

	def update_opportunity(self, status):
		for opportunity in set(d.prevdoc_docname for d in self.get("items")):
			if opportunity:
				self.update_opportunity_status(status, opportunity)

		if self.opportunity:
			self.update_opportunity_status(status)

	def update_opportunity_status(self, status, opportunity=None):
		if not opportunity:
			opportunity = self.opportunity

		opp = frappe.get_doc("Opportunity", opportunity)
		opp.set_status(status=status, update=True)

	@frappe.whitelist()
	def send_quotation(self):
		# Create approval id
		str_uuid = str(uuid.uuid4())
		self.approval_id = str_uuid
		self.save()

		if (not self.contact_email and not self.cc_email):
			frappe.msgprint(_("Could not find email to send information"))
		else:
			# Send Email
			self.send_quotation_email()

		if	(not self.contact_mobile and not self.cc_mobile):
			frappe.msgprint(_("Could not find mobile phone to send information"))
		else:
			#Send sms
			self.send_quotation_sms()
			
		# if self.contact_person:
		# 	if not self.contact_email and not self.contact_mobile:
		# 		frappe.msgprint(_("Could not find email or mobile phone to send information"))
		# 	else:
		# 		# Send Email
		# 		self.send_quotation_email()
		# 		# Send sms
		# 		self.send_quotation_sms()
		# else:
		# 	frappe.msgprint(_("Could not find email or mobile phone to send information"))
	
	@frappe.whitelist()
	def send_quotation_email(self):
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
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/quotation/" + self.approval_id

			#Get template
			template = frappe.db.get_value('Push Email Template', {'reference_type':'Quotation','template':'MAU-001'}, ['subject','body'], as_dict=1)
			body = template.body.replace('{{link}}', approval_url)
			body = body.replace('{{link_name}}', self.name)

			#customer
			refCongty = frappe.get_doc('Customer', self.party_name)
			body = body.replace('{{company_name}}', refCongty.company_name)

			body = body.replace('{{task_name}}', self.task_description)
			body = body.replace('{{yyyy}}', self.items[0].year_text)

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
			push_email.reference_type = "Quotation"
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
					'reference_doctype': 'Quotation',
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
	def send_quotation_sms(self):
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
			approval_url = frappe.db.get_single_value("Approval Settings","approval_url") + "/quotation/" + self.approval_id

			#Get template
			template = frappe.db.get_value('Push SMS Template', {'reference_type':'Quotation','template':'MAU-001'}, ['body'], as_dict=1)
			body = template.body.replace('{{link}}', approval_url)

			#customer
			refCongty = frappe.get_doc('Customer', self.party_name)
			body = body.replace('{{company_name}}', refCongty.company_name)

			body = body.replace('{{task_name}}', self.task_description)
			body = body.replace('{{yyyy}}', self.items[0].year_text)

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
				push_sms.reference_type = "Quotation"
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
						'reference_doctype': 'Quotation',
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
	def create_contract(self):
		# Nam ket thuc
		to_year = 1900
		year_text = ""
		for items in self.items:
			to_year = items.to_year
			year_text = items.year_text
		# Tao hop dong
		ct = frappe.new_doc('Contract')
		ct.contract_number = self.name.replace('BG-TARGET', 'HD-TARGET')
		ct.party_type = "Customer"
		ct.party_name = self.party_name
		ct.report_end_date = date(to_year,12,31)
		ct.total = self.total
		ct.grand_total = self.grand_total
		ct.deadline = 15
		ct.represent_name = self.represent_name
		ct.position = self.position
		ct.contact_mobile = self.contact_mobile
		ct.contact_email = self.contact_email
		ct.document_type = self.doctype
		ct.document_name = self.name
		ct.year_text = year_text
		ct.end_year = to_year
		ct.insert()
		# Luu hop dong
		self.contract = ct.name
		self.save(ignore_version=True)
		return ct.name

	@frappe.whitelist()
	def declare_enquiry_lost(self, lost_reasons_list, competitors, detailed_reason=None):
		if not (self.is_fully_ordered() or self.is_partially_ordered()):
			get_lost_reasons = frappe.get_list("Quotation Lost Reason", fields=["name"])
			lost_reasons_lst = [reason.get("name") for reason in get_lost_reasons]
			self.db_set("status", "Lost")

			if detailed_reason:
				self.db_set("order_lost_reason", detailed_reason)

			for reason in lost_reasons_list:
				if reason.get("lost_reason") in lost_reasons_lst:
					self.append("lost_reasons", reason)
				else:
					frappe.throw(
						_("Invalid lost reason {0}, please create a new lost reason").format(
							frappe.bold(reason.get("lost_reason"))
						)
					)

			for competitor in competitors:
				self.append("competitors", competitor)

			self.update_opportunity("Lost")
			self.update_lead()
			self.save()

		else:
			frappe.throw(_("Cannot set as Lost as Sales Order is made."))

	def on_submit(self):
		# Check for Approving Authority
		frappe.get_doc("Authorization Control").validate_approving_authority(
			self.doctype, self.company, self.base_grand_total, self
		)

		# update enquiry status
		self.update_opportunity("Quotation")
		self.update_lead()

	def on_cancel(self):
		if self.lost_reasons:
			self.lost_reasons = []
		super(Quotation, self).on_cancel()

		# update enquiry status
		self.set_status(update=True)
		self.update_opportunity("Open")
		self.update_lead()

	def print_other_charges(self, docname):
		print_lst = []
		for d in self.get("taxes"):
			lst1 = []
			lst1.append(d.description)
			lst1.append(d.total)
			print_lst.append(lst1)
		return print_lst

	def on_recurring(self, reference_doc, auto_repeat_doc):
		self.valid_till = None

	def get_rows_with_alternatives(self):
		rows_with_alternatives = []
		table_length = len(self.get("items"))

		for idx, row in enumerate(self.get("items")):
			if row.is_alternative:
				continue

			if idx == (table_length - 1):
				break

			if self.get("items")[idx + 1].is_alternative:
				rows_with_alternatives.append(row.name)

		return rows_with_alternatives

	@frappe.whitelist()
	def attach_pdf(doc, event=None):
		template_to_pdf(doc, event=None)

	@frappe.whitelist()
	def	make_quotation_number(doc, event=None):
		if doc.invoice == 'Xuất hóa đơn':
			mm_yyyy = datetime.today().strftime("%m-%Y")
			str_mm_yyyy = "-" + mm_yyyy
		else:
			mm_yyyy = datetime.today().strftime("%m%Y")
			str_mm_yyyy = mm_yyyy
		searchStr = '%' + mm_yyyy + '/BG-TARGET' + '%'
		result = frappe.db.sql(f"""SELECT Max(name) as QuoteNum FROM `tabQuotation` WHERE `name` LIKE '{searchStr}'""")
		if str(result) == '((None,),)':
			return "0001" + str_mm_yyyy + '/BG-TARGET'
		else:
			return str(int(str(result)[3:7])+1).zfill(4) + str_mm_yyyy + '/BG-TARGET'
			
	@frappe.whitelist()
	def update_in_words(doc, event=None):
		words_vn = num2words(doc.grand_total, lang='vi').capitalize()+" đồng"
		words_en = num2words(doc.grand_total, lang='en').capitalize()+" dong"
		doc.in_words_vn = words_vn
		doc.in_words_en = words_en
		doc.save()

	@frappe.whitelist()
	def get_customer_doc(self):
		ref = frappe.get_doc("Customer",self.party_name)
		return ref
	
	@frappe.whitelist()
	def get_email_global(self):
		g_email = frappe.db.get_single_value("Push Email Settings","global_email")
		return g_email
	
	@frappe.whitelist()
	def get_territory_doc(self):
		refCustomer = frappe.get_doc("Customer",self.party_name)
		ref = frappe.get_doc("Territory",refCustomer.territory)
		return ref

def get_list_context(context=None):
	from erpnext.controllers.website_list_for_contact import get_list_context

	list_context = get_list_context(context)
	list_context.update(
		{
			"show_sidebar": True,
			"show_search": True,
			"no_breadcrumbs": True,
			"title": _("Quotations"),
		}
	)

	return list_context


@frappe.whitelist()
def make_sales_order(source_name: str, target_doc=None):
	if not frappe.db.get_singles_value(
		"Selling Settings", "allow_sales_order_creation_for_expired_quotation"
	):
		quotation = frappe.db.get_value(
			"Quotation", source_name, ["transaction_date", "valid_till"], as_dict=1
		)
		if quotation.valid_till and (
			quotation.valid_till < quotation.transaction_date or quotation.valid_till < getdate(nowdate())
		):
			frappe.throw(_("Validity period of this quotation has ended."))

	return _make_sales_order(source_name, target_doc)


def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
	customer = _make_customer(source_name, ignore_permissions)
	ordered_items = frappe._dict(
		frappe.db.get_all(
			"Sales Order Item",
			{"prevdoc_docname": source_name, "docstatus": 1},
			["item_code", "sum(qty)"],
			group_by="item_code",
			as_list=1,
		)
	)

	selected_rows = [x.get("name") for x in frappe.flags.get("args", {}).get("selected_items", [])]

	def set_missing_values(source, target):
		if customer:
			target.customer = customer.name
			target.customer_name = customer.customer_name
		if source.referral_sales_partner:
			target.sales_partner = source.referral_sales_partner
			target.commission_rate = frappe.get_value(
				"Sales Partner", source.referral_sales_partner, "commission_rate"
			)

		# sales team
		for d in customer.get("sales_team") or []:
			target.append(
				"sales_team",
				{
					"sales_person": d.sales_person,
					"allocated_percentage": d.allocated_percentage or None,
					"commission_rate": d.commission_rate,
				},
			)

		target.flags.ignore_permissions = ignore_permissions
		target.delivery_date = nowdate()
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(obj, target, source_parent):
		balance_qty = obj.qty - ordered_items.get(obj.item_code, 0.0)
		target.qty = balance_qty if balance_qty > 0 else 0
		target.stock_qty = flt(target.qty) * flt(obj.conversion_factor)
		target.delivery_date = nowdate()

		if obj.against_blanket_order:
			target.against_blanket_order = obj.against_blanket_order
			target.blanket_order = obj.blanket_order
			target.blanket_order_rate = obj.blanket_order_rate

	def can_map_row(item) -> bool:
		"""
		Row mapping from Quotation to Sales order:
		1. If no selections, map all non-alternative rows (that sum up to the grand total)
		2. If selections: Is Alternative Item/Has Alternative Item: Map if selected and adequate qty
		3. If selections: Simple row: Map if adequate qty
		"""
		has_qty = item.qty > 0

		if not selected_rows:
			return not item.is_alternative

		if selected_rows and (item.is_alternative or item.has_alternative_item):
			return (item.name in selected_rows) and has_qty

		# Simple row
		return has_qty

	doclist = get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {"doctype": "Sales Order", "validation": {"docstatus": ["=", 1]}},
			"Quotation Item": {
				"doctype": "Sales Order Item",
				"field_map": {"parent": "prevdoc_docname", "name": "quotation_item"},
				"postprocess": update_item,
				"condition": can_map_row,
			},
			"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "add_if_empty": True},
			"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
			"Payment Schedule": {"doctype": "Payment Schedule", "add_if_empty": True},
		},
		target_doc,
		set_missing_values,
		ignore_permissions=ignore_permissions,
	)

	# postprocess: fetch shipping address, set missing values
	doclist.set_onload("ignore_price_list", True)

	return doclist


def set_expired_status():
	# filter out submitted non expired quotations whose validity has been ended
	cond = "`tabQuotation`.docstatus = 1 and `tabQuotation`.status NOT IN ('Expired', 'Lost') and `tabQuotation`.valid_till < %s"
	# check if those QUO have SO against it
	so_against_quo = """
		SELECT
			so.name FROM `tabSales Order` so, `tabSales Order Item` so_item
		WHERE
			so_item.docstatus = 1 and so.docstatus = 1
			and so_item.parent = so.name
			and so_item.prevdoc_docname = `tabQuotation`.name"""

	# if not exists any SO, set status as Expired
	frappe.db.multisql(
		{
			"mariadb": """UPDATE `tabQuotation`  SET `tabQuotation`.status = 'Expired' WHERE {cond} and not exists({so_against_quo})""".format(
				cond=cond, so_against_quo=so_against_quo
			),
			"postgres": """UPDATE `tabQuotation` SET status = 'Expired' FROM `tabSales Order`, `tabSales Order Item` WHERE {cond} and not exists({so_against_quo})""".format(
				cond=cond, so_against_quo=so_against_quo
			),
		},
		(nowdate()),
	)


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
	return _make_sales_invoice(source_name, target_doc)

def _make_sales_invoice(source_name, target_doc=None, ignore_permissions=False):
	customer = _make_customer(source_name, ignore_permissions)

	def set_missing_values(source, target):
		if customer:
			target.customer = customer.name
			target.customer_name = customer.customer_name

		target.flags.ignore_permissions = ignore_permissions
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(obj, target, source_parent):
		target.cost_center = None
		target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)

	doclist = get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {"doctype": "Sales Invoice", "validation": {"docstatus": ["=", 1]}},
			"Quotation Item": {
				"doctype": "Sales Invoice Item",
				"postprocess": update_item,
				"condition": lambda row: not row.is_alternative,
			},
			"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "add_if_empty": True},
			"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
		},
		target_doc,
		set_missing_values,
		ignore_permissions=ignore_permissions,
	)

	doclist.set_onload("ignore_price_list", True)

	return doclist


def _make_customer(source_name, ignore_permissions=False):
	quotation = frappe.db.get_value(
		"Quotation", source_name, ["order_type", "party_name", "customer_name"], as_dict=1
	)

	if quotation and quotation.get("party_name"):
		if not frappe.db.exists("Customer", quotation.get("party_name")):
			lead_name = quotation.get("party_name")
			customer_name = frappe.db.get_value(
				"Customer", {"lead_name": lead_name}, ["name", "customer_name"], as_dict=True
			)
			if not customer_name:
				from erpnext.crm.doctype.lead.lead import _make_customer

				customer_doclist = _make_customer(lead_name, ignore_permissions=ignore_permissions)
				customer = frappe.get_doc(customer_doclist)
				customer.flags.ignore_permissions = ignore_permissions
				if quotation.get("party_name") == "Shopping Cart":
					customer.customer_group = frappe.db.get_value(
						"E Commerce Settings", None, "default_customer_group"
					)

				try:
					customer.insert()
					return customer
				except frappe.NameError:
					if frappe.defaults.get_global_default("cust_master_name") == "Customer Name":
						customer.run_method("autoname")
						customer.name += "-" + lead_name
						customer.insert()
						return customer
					else:
						raise
				except frappe.MandatoryError as e:
					mandatory_fields = e.args[0].split(":")[1].split(",")
					mandatory_fields = [customer.meta.get_label(field.strip()) for field in mandatory_fields]

					frappe.local.message_log = []
					lead_link = frappe.utils.get_link_to_form("Lead", lead_name)
					message = (
						_("Could not auto create Customer due to the following missing mandatory field(s):") + "<br>"
					)
					message += "<br><ul><li>" + "</li><li>".join(mandatory_fields) + "</li></ul>"
					message += _("Please create Customer from Lead {0}.").format(lead_link)

					frappe.throw(message, title=_("Mandatory Missing"))
			else:
				return customer_name
		else:
			return frappe.get_doc("Customer", quotation.get("party_name"))
		
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