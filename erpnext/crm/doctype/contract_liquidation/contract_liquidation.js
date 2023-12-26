// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Liquidation", {
	refresh: function (frm) {
		if (
			frm.doc.workflow_state == "Awaiting for response" &&
			frm.doc.unsigned_file
		) {
			frm.add_custom_button(__("Resend Email"), () => {
				frm.call("send_contract_liquidation_email").then(() => {
					// frappe.msgprint(__("Email sent succesfully"));
				});
			});
			frm.add_custom_button(__("Resend SMS"), () => {
				frm.call("send_contract_liquidation_sms").then(() => {
					// frappe.msgprint(__("Email sent succesfully"));
				});
			});
		}
	},
	setup: function (frm) {
		cur_frm.fields_dict["print_template"].get_query = function (doc) {
			return {
				filters: {
					doc_type: "Contract Liquidation",
				},
			};
		};
		cur_frm.fields_dict["contract_number"].get_query = function (doc) {
			return {
				filters: {
					workflow_state: "Approved",
					contract_liquidation: "",
				},
			};
		};
	},
	contract_number: function (frm) {
		if (frm.doc.contract_number == "") {
			frm.set_value("cl_number", "");
			frm.set_value("customer", "");
			frm.set_value("represent_name", "");
			frm.set_value("position", "");
			frm.set_value("contact_mobile", "");
			frm.set_value("contact_email", "");
			frm.set_value("cc_mobile", "");
			frm.set_value("cc_email", "");
			frm.set_value("remaining", "");
		} else {
			frm.call("link_contract_data").then((r) => {
				var str = JSON.stringify(r);
				var json = JSON.parse(str);
				var ref = json.message;
				frm.set_value(
					"cl_number",
					ref.name.replace("HD-TARGET", "BBTL-TARGET")
				);
				frm.set_value("customer", ref.party_name);
				frm.set_value("represent_name", ref.represent_name);
				frm.set_value("position", ref.position);
				frm.set_value("contact_mobile", ref.contact_mobile);
				frm.set_value("contact_email", ref.contact_email);
				frm.set_value("cc_mobile", ref.cc_mobile);
				frm.set_value("cc_email", ref.cc_email);
				frm.call("get_quotation_doc").then((r) => {
					var str = JSON.stringify(r);
					var json = JSON.parse(str);
					var refQuotation = json.message;
					frm.set_value(
						"remaining",
						refQuotation.grand_total - frm.doc.paid
					);
					if (!ref.contact_mobile && !ref.contact_email) {
						frm.call("get_customer_doc").then((r) => {
							var str = JSON.stringify(r);
							var json = JSON.parse(str);
							var refCustomer = json.message;
							frm.set_value(
								"contact_mobile",
								refCustomer.mobile_no
							);
							frm.set_value(
								"contact_email",
								refCustomer.email_id
							);
						});
					}
				});
			});
		}
		// frm.refresh();
	},
	get_territory_info: function (frm) {
		frm.call("get_territory_doc").then((r) => {
			var str = JSON.stringify(r);
			var json = JSON.parse(str);
			var ref = json.message;
			frm.set_value("cc_mobile", ref.mobile);
			frm.set_value("cc_email", ref.email);
		});
	},
	paid: function (frm) {
		frm.call("get_quotation_doc").then((r) => {
			var str = JSON.stringify(r);
			var json = JSON.parse(str);
			var ref = json.message;
			frm.set_value("remaining", ref.grand_total - frm.doc.paid);
		});
		// frm.refresh();
	},
	before_workflow_action: (frm) => {
		frappe.dom.unfreeze();
		if (frm.doc.workflow_state == "Draft") {
			if (frm.selected_workflow_action == "Send") {
				if (!frm.doc.unsigned_file) {
					frappe.throw(
						__(
							"Please attach a contract liquidation file or create a file from the template"
						)
					);
				}
				this.frm.call("send_contract_liquidation").then(() => {
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
		frm.call("update_ref_contract").then((r) => {
			// console.log(r)
		});
	},
});
