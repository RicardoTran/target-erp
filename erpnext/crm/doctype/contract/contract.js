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
		cur_frm.fields_dict['document_name'].get_query = function(doc) {
			if(doc.document_type=="Quotation") {
				return {
					filters: {
						"workflow_state": 'Approved',
						"contract":''
					}
				}
			}
		}
	},
	document_type: function(frm) {
		frm.set_value('document_name','')
	},
	document_name: function(frm) {
		if (frm.doc.document_name == '') {
			frm.set_value('contract_number','')
			frm.set_value('party_type','Customer')
			frm.set_value('party_name','')
			frm.set_value('report_end_date','')
			frm.set_value('date','')
			frm.set_value('deadline','')
			frm.set_value('represent_name','')
			frm.set_value('position','')
			frm.set_value('contact_mobile','')
			frm.set_value('contact_email','')
			frm.set_value('year_text','')
		} else {
			if (frm.doc.document_type == "Quotation") {
				let end_date = new Date(ref.items[0].to_year,11,31)
				let date_now = new Date()
				frm.call("link_quotation_data").then((r) =>{
					var str = JSON.stringify(r)
					var json = JSON.parse(str)
					var ref = json.message
					frm.set_value('contract_number',ref.name.replace('BG-TARGET', 'HD-TARGET'))
					frm.set_value('party_type','Customer')
					frm.set_value('party_name',ref.party_name)
					frm.set_value('report_end_date',end_date)
					frm.set_value('date',date_now)
					frm.set_value('deadline',15)
					frm.set_value('represent_name',ref.represent_name)
					frm.set_value('position',ref.position)
					frm.set_value('contact_mobile',ref.contact_mobile)
					frm.set_value('contact_email',ref.contact_email)
					frm.set_value('year_text',ref.year_text)
				})
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
	},
	before_save: function(frm) {
		frm.call("update_ref_quotation").then((r) =>{
			console.log(r)
		})
	}
});
