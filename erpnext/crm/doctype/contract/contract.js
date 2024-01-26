// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract", {
	contract_template: function (frm) {
		if (frm.doc.contract_template) {
			frappe.call({
				method: "erpnext.crm.doctype.contract_template.contract_template.get_contract_template",
				args: {
					template_name: frm.doc.contract_template,
					doc: frm.doc,
				},
				callback: function (r) {
					if (r && r.message) {
						let contract_template = r.message.contract_template;
						frm.set_value(
							"contract_terms",
							r.message.contract_terms
						);
						frm.set_value(
							"requires_fulfilment",
							contract_template.requires_fulfilment
						);

						if (frm.doc.requires_fulfilment) {
							// Populate the fulfilment terms table from a contract template, if any
							r.message.contract_template.fulfilment_terms.forEach(
								(element) => {
									let d = frm.add_child("fulfilment_terms");
									d.requirement = element.requirement;
								}
							);
							frm.refresh_field("fulfilment_terms");
						}
					}
				},
			});
		}
	},
	refresh: function (frm) {
		if (
			frm.doc.workflow_state == "Awaiting for response" &&
			frm.doc.unsigned_file
		) {
			frm.add_custom_button(__("Resend Email"), () => {
				frm.call("send_contract_email").then(() => {
					// frappe.msgprint(__("Email sent succesfully"));
				});
			});
			frm.add_custom_button(__("Resend SMS"), () => {
				frm.call("send_contract_sms").then(() => {
					// frappe.msgprint(__("Email sent succesfully"));
				});
			});
		}
		if (
			frm.doc.workflow_state == "Approved" &&
			!frm.doc.contract_liquidation
		) {
			frm.add_custom_button(__("Create Contract Liquidation"), () => {
				frappe.new_doc(
					"Contract Liquidation",
					{
						document_type: "Quotation Liquidation",
						contract_number: frm.doc.name,
					},
					(doc) => {}
				);
			});
		}
	},
	setup: function (frm) {
		cur_frm.fields_dict["print_template"].get_query = function (doc) {
			return {
				filters: {
					doc_type: "Contract",
				},
			};
		};
		cur_frm.fields_dict["document_name"].get_query = function (doc) {
			if (doc.document_type == "Quotation") {
				return {
					filters: {
						workflow_state: "Approved",
						contract: "",
					},
				};
			}
		};
	},
	document_type: function (frm) {
		frm.set_value("document_name", "");
	},
	document_name: function (frm) {
		if (frm.doc.document_name == "") {
			frm.set_value("contract_number", "");
			frm.set_value("party_type", "Customer");
			frm.set_value("party_name", "");
			frm.set_value("report_end_date", "");
			frm.set_value("total", 0);
			frm.set_value("grand_total", 0);
			frm.set_value("deadline", "");
			frm.set_value("represent_name", "");
			frm.set_value("position", "");
			frm.set_value("contact_mobile", "");
			frm.set_value("contact_email", "");
			frm.set_value("cc_mobile", "");
			frm.set_value("cc_email", "");
			frm.set_value("year_text", "");
		} else {
			if (frm.doc.document_type == "Quotation") {
				frm.call("link_quotation_data").then((r) => {
					var str = JSON.stringify(r);
					var json = JSON.parse(str);
					var ref = json.message;
					frm.set_value(
						"contract_number",
						ref.name.replace("BG-TARGET", "HD-TARGET")
					);
					frm.set_value("party_type", "Customer");
					frm.set_value("party_name", ref.party_name);
					frm.set_value(
						"report_end_date",
						ref.items[0].to_year + "-12-31"
					);
					frm.set_value("total", ref.total);
					frm.set_value("grand_total", ref.grand_total);
					frm.set_value("deadline", 15);
					frm.set_value("represent_name", ref.represent_name);
					frm.set_value("position", ref.position);
					frm.set_value("contact_mobile", ref.contact_mobile);
					frm.set_value("contact_email", ref.contact_email);
					frm.set_value("cc_mobile", ref.cc_mobile);
					frm.set_value("cc_email", ref.cc_email);
					frm.set_value("year_text", ref.year_text);
					frm.set_value("end_year", ref.items[0].to_year);
					if (!ref.contact_mobile && !ref.contact_email) {
						frm.call("get_customer_doc").then((r) => {
							var str = JSON.stringify(r);
							var json = JSON.parse(str);
							var ref = json.message;
							frm.set_value("contact_mobile", ref.mobile_no);
							frm.set_value("contact_email", ref.email_id);
						});
					}
				});
			}
		}
		// frm.refresh();
	},
	get_territory_info: function (frm) {
		frm.call("get_territory_doc").then((r) => {
			var str = JSON.stringify(r);
			var json = JSON.parse(str);
			var ref = json.message;
			frm.set_value("cc_mobile", ref.mobile);
			frm.call("get_email_global").then((r) => {
				var list_email =
					ref.email +
					"," +
					frappe.session.user_email +
					"," +
					r.message;
				list_email = list_email.replace("undefined,", "");
				list_email = list_email.replace("undefined", "");
				frm.set_value("cc_email", list_email);
			});
		});
	},
	get_primary_contact: function (frm) {
		frm.call("get_customer_doc").then((r) => {
			var str = JSON.stringify(r);
			var json = JSON.parse(str);
			var ref = json.message;
			frm.set_value("contact_mobile", ref.mobile_no);
			frm.set_value("contact_email", ref.email_id);
		});
	},
	before_workflow_action: (frm) => {
		frappe.dom.unfreeze();
		if (frm.doc.workflow_state == "Draft") {
			if (frm.selected_workflow_action == "Send") {
				if (!frm.doc.unsigned_file) {
					frappe.throw(
						__(
							"Please attach a contract file or create a file from the template"
						)
					);
				}
				this.frm.call("send_contract").then(() => {
					// frappe.msgprint(__("Email sent succesfully"));
				});
			}
		}
	},
	create_pdf: function (frm) {
		frappe.call({
			doc: frm.doc,
			method: "attach_pdf",
			// callback: function(r, rt) {
			//    //call back operation
			// }
		});
		frm.reload_doc();
	},
	after_save: function (frm) {
		frm.call("update_ref_quotation").then((r) => {
			// console.log(r)
		});
	},
});
