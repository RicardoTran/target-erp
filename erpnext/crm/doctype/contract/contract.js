// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract", {
	contract_template: function (frm) {
		if (frm.doc.contract_template) {
			frappe.call({
				method: 'erpnext.crm.doctype.contract_template.contract_template.get_contract_template',
				args: {
					template_name: frm.doc.contract_template,
					doc: frm.doc
				},
				callback: function(r) {
					if (r && r.message) {
						let contract_template = r.message.contract_template;
						frm.set_value("contract_terms", r.message.contract_terms);
						frm.set_value("requires_fulfilment", contract_template.requires_fulfilment);

						if (frm.doc.requires_fulfilment) {
							// Populate the fulfilment terms table from a contract template, if any
							r.message.contract_template.fulfilment_terms.forEach(element => {
								let d = frm.add_child("fulfilment_terms");
								d.requirement = element.requirement;
							});
							frm.refresh_field("fulfilment_terms");
						}
					}
				}
			});
		}
	},
	refresh: function(frm) {
		if(frm.doc.workflow_state == "Awaiting for response" && frm.doc.unsigned_file) {
			frm.add_custom_button(__("Resend Email"), () => {
				frm.call("send_contract_email").then(() =>{
					// frappe.msgprint(__("Email sent succesfully"));
				});
			});
			frm.add_custom_button(__("Resend SMS"), () => {
				frm.call("send_contract_sms").then(() =>{
					// frappe.msgprint(__("Email sent succesfully"));
				});
			})
		};
	},
	setup: function(frm) {
		cur_frm.fields_dict['print_template'].get_query = function(doc) {
			return {
				filters: {
					"doc_type": 'Contract'
				}
			}
		}
	},
	before_workflow_action: (frm) => {
		frappe.dom.unfreeze()
		if (frm.doc.workflow_state == "Draft") {
			if (frm.selected_workflow_action == "Send") {
				if (!frm.doc.unsigned_file){
					frappe.throw(__("Please attach a contract file or create a file from the template"))
				}
				this.frm.call("send_contract").then(() =>{
					// frappe.msgprint(__("Email sent succesfully"));
				});
			}
		}
	},
	create_pdf: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'attach_pdf'
			// callback: function(r, rt) {
			//    //call back operation
			// }
		  })
		frm.reload_doc()	  
	}
});
