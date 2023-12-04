// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

{% include 'erpnext/selling/sales_common.js' %}

frappe.ui.form.on('Quotation', {

	setup: function(frm) {
		frm.custom_make_buttons = {
			'Sales Order': 'Sales Order'
		},

		frm.set_query("quotation_to", function() {
			return{
				"filters": {
					"name": ["in", ["Customer", "Lead", "Prospect"]],
				}
			}
		});

		frm.set_df_property('packed_items', 'cannot_add_rows', true);
		frm.set_df_property('packed_items', 'cannot_delete_rows', true);

		frm.set_query('company_address', function(doc) {
			if(!doc.company) {
				frappe.throw(__('Please set Company'));
			}

			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Company',
					link_name: doc.company
				}
			};
		});
		cur_frm.fields_dict['print_template'].get_query = function(doc) {
			return {
				filters: {
					"doc_type": 'Quotation'
				}
			}
		}
	},

	refresh: function(frm) {
		frm.trigger("set_label");
		frm.trigger("set_dynamic_field_label");
	},
	onload: function(frm) {
		//Set so bao gia
		if (frm.is_new()) {
			frm.call("make_quotation_number").then((r) =>{
				frm.set_value("quotation_number",r.message)
			});
		}
	},
	quotation_to: function(frm) {
		frm.trigger("set_label");
		frm.trigger("toggle_reqd_lead_customer");
		frm.trigger("set_dynamic_field_label");
	},

	party_name: function(frm) {
		if (frm.doc.party_name) {
			var ref
			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "Customer",
					name: frm.doc.party_name,
				},
				callback: function(r) {
					if (r && r.message) {
						let ref = r.message
						console.log(ref)
						frm.set_value('represent_name',ref.represent_name)
						frm.set_value('position',ref.position)
					}
				}
			})
		}
		else {
			frm.set_value('represent_name','')
			frm.set_value('position','')
		}
	},

	before_workflow_action: (frm) => {
		frappe.dom.unfreeze()
		if (frm.doc.workflow_state == "Draft") {
			if (frm.selected_workflow_action == "Send") {
				if (!frm.doc.unsigned_file){
					frappe.throw(__("Please attach a quote file or create a file from the template"))
				}
				this.frm.call("send_quotation").then(() =>{
					// frappe.msgprint(__("Email sent succesfully"));
				});
			}
		}
		if (frm.doc.workflow_state == "Awaiting for response") {
			if (frm.selected_workflow_action == "Reject") {
				this.frm.trigger('set_as_lost_dialog');
			}
		}
	},
	
	set_label: function(frm) {
		frm.fields_dict.customer_address.set_label(__(frm.doc.quotation_to + " Address"));
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
	after_save: function(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'update_in_words'
		  })
	}
});

erpnext.selling.QuotationController = class QuotationController extends erpnext.selling.SellingController {
	onload(doc, dt, dn) {
		super.onload(doc, dt, dn);
	}
	party_name() {
		var me = this;
		erpnext.utils.get_party_details(this.frm, null, null, function() {
			me.apply_price_list();
		});

		if(me.frm.doc.quotation_to=="Lead" && me.frm.doc.party_name) {
			me.frm.trigger("get_lead_details");
		}
	}
	refresh(doc, dt, dn) {
		super.refresh(doc, dt, dn);
		frappe.dynamic_link = {
			doc: this.frm.doc,
			fieldname: 'party_name',
			doctype: doc.quotation_to == 'Customer' ? 'Customer' : 'Lead',
		};

		var me = this;

		if (doc.__islocal && !doc.valid_till) {
			if(frappe.boot.sysdefaults.quotation_valid_till){
				this.frm.set_value('valid_till', frappe.datetime.add_days(doc.transaction_date, frappe.boot.sysdefaults.quotation_valid_till));
			} else {
				this.frm.set_value('valid_till', frappe.datetime.add_months(doc.transaction_date, 1));
			}
		};

		if(doc.workflow_state == "Awaiting for response" && doc.unsigned_file) {
			this.frm.add_custom_button(__("Resend Email"), () => {
				this.frm.call("send_quotation_email").then(() =>{
					// frappe.msgprint(__("Email sent succesfully"));
				});
			});
			this.frm.add_custom_button(__("Resend SMS"), () => {
				this.frm.call("send_quotation_sms").then(() =>{
					// frappe.msgprint(__("Email sent succesfully"));
				});
			})
		};
		if(doc.workflow_state == "Approved" && !doc.contract) {
			this.frm.add_custom_button(__("Create Contract"), () => {
				// this.frm.call("create_contract").then((r) =>{
				// 	var str = JSON.stringify(r);
				// 	var json = JSON.parse(str);
				// 	// console.log(json.message);
				// 	frappe.set_route("Form","Contract",json.message);
				// });
				var to_year = doc.items[0].to_year
				frappe.new_doc('Contract', {
					document_type: 'Quotation',
					document_name: doc.name,
					contract_number: doc.name.replace('BG-TARGET', 'HD-TARGET'),
					party_type: 'Customer',
					party_name: doc.party_name,
					represent_name: doc.represent_name,
					position: doc.position,
					contact_mobile: doc.contact_mobile,
					contact_email: doc.contact_email,
					year_text: doc.year_text,
				}, doc => {
					doc.deadline = 15;
					doc.report_end_date = to_year + '-12-31';
					doc.end_year = to_year
				})
			})
			
		};

		// if (doc.docstatus == 1 && !["Lost", "Ordered"].includes(doc.status)) {
		// 	if (frappe.boot.sysdefaults.allow_sales_order_creation_for_expired_quotation
		// 		|| (!doc.valid_till)
		// 		|| frappe.datetime.get_diff(doc.valid_till, frappe.datetime.get_today()) >= 0) {
		// 			this.frm.add_custom_button(
		// 				__("Sales Order"),
		// 				() => this.make_sales_order(),
		// 				__("Create")
		// 			);
		// 		}

		// 	if(doc.status!=="Ordered") {
		// 		this.frm.add_custom_button(__('Set as Lost'), () => {
		// 				this.frm.trigger('set_as_lost_dialog');
		// 			});
		// 		}

		// 	if(!doc.auto_repeat) {
		// 		cur_frm.add_custom_button(__('Subscription'), function() {
		// 			erpnext.utils.make_subscription(doc.doctype, doc.name)
		// 		}, __('Create'))
		// 	}

		// 	cur_frm.page.set_inner_btn_group_as_primary(__('Create'));
		// }

		// if (this.frm.doc.docstatus===0) {
		// 	this.frm.add_custom_button(__('Opportunity'),
		// 		function() {
		// 			erpnext.utils.map_current_doc({
		// 				method: "erpnext.crm.doctype.opportunity.opportunity.make_quotation",
		// 				source_doctype: "Opportunity",
		// 				target: me.frm,
		// 				setters: [
		// 					{
		// 						label: "Party",
		// 						fieldname: "party_name",
		// 						fieldtype: "Link",
		// 						options: me.frm.doc.quotation_to,
		// 						default: me.frm.doc.party_name || undefined
		// 					},
		// 					{
		// 						label: "Opportunity Type",
		// 						fieldname: "opportunity_type",
		// 						fieldtype: "Link",
		// 						options: "Opportunity Type",
		// 						default: me.frm.doc.order_type || undefined
		// 					}
		// 				],
		// 				get_query_filters: {
		// 					status: ["not in", ["Lost", "Closed"]],
		// 					company: me.frm.doc.company
		// 				}
		// 			})
		// 		}, __("Get Items From"), "btn-default");
		// }

		this.toggle_reqd_lead_customer();

	}

	make_sales_order() {
		var me = this;

		let has_alternative_item = this.frm.doc.items.some((item) => item.is_alternative);
		if (has_alternative_item) {
			this.show_alternative_items_dialog();
		} else {
			frappe.model.open_mapped_doc({
				method: "erpnext.selling.doctype.quotation.quotation.make_sales_order",
				frm: me.frm
			});
		}
	}

	set_dynamic_field_label(){
		if (this.frm.doc.quotation_to == "Customer") {
			this.frm.set_df_property("party_name", "label", "Customer");
			this.frm.fields_dict.party_name.get_query = null;
		} else if (this.frm.doc.quotation_to == "Lead") {
			this.frm.set_df_property("party_name", "label", "Lead");
			this.frm.fields_dict.party_name.get_query = function() {
				return{	query: "erpnext.controllers.queries.lead_query" }
			}
		} else if (this.frm.doc.quotation_to == "Prospect") {
			this.frm.set_df_property("party_name", "label", "Prospect");
		}
	}

	toggle_reqd_lead_customer() {
		var me = this;

		// to overwrite the customer_filter trigger from queries.js
		this.frm.toggle_reqd("party_name", this.frm.doc.quotation_to);
		this.frm.set_query('customer_address', this.address_query);
		this.frm.set_query('shipping_address_name', this.address_query);
	}

	tc_name() {
		this.get_terms();
	}

	address_query(doc) {
		return {
			query: 'frappe.contacts.doctype.address.address.address_query',
			filters: {
				link_doctype: frappe.dynamic_link.doctype,
				link_name: doc.party_name
			}
		};
	}

	validate_company_and_party(party_field) {
		if(!this.frm.doc.quotation_to) {
			frappe.msgprint(__("Please select a value for {0} quotation_to {1}", [this.frm.doc.doctype, this.frm.doc.name]));
			return false;
		} else if (this.frm.doc.quotation_to == "Lead") {
			return true;
		} else {
			return super.validate_company_and_party(party_field);
		}
	}

	get_lead_details() {
		var me = this;
		if(!this.frm.doc.quotation_to === "Lead") {
			return;
		}

		frappe.call({
			method: "erpnext.crm.doctype.lead.lead.get_lead_details",
			args: {
				'lead': this.frm.doc.party_name,
				'posting_date': this.frm.doc.transaction_date,
				'company': this.frm.doc.company,
			},
			callback: function(r) {
				if(r.message) {
					me.frm.updating_party_details = true;
					me.frm.set_value(r.message);
					me.frm.refresh();
					me.frm.updating_party_details = false;

				}
			}
		})
	}

	show_alternative_items_dialog() {
		let me = this;

		const table_fields = [
		{
			fieldtype:"Data",
			fieldname:"name",
			label: __("Name"),
			read_only: 1,
		},
		{
			fieldtype:"Link",
			fieldname:"item_code",
			options: "Item",
			label: __("Item Code"),
			read_only: 1,
			in_list_view: 1,
			columns: 2,
			formatter: (value, df, options, doc) => {
				return doc.is_alternative ? `<span class="indicator yellow">${value}</span>` : value;
			}
		},
		{
			fieldtype:"Data",
			fieldname:"description",
			label: __("Description"),
			in_list_view: 1,
			read_only: 1,
		},
		{
			fieldtype:"Currency",
			fieldname:"amount",
			label: __("Amount"),
			options: "currency",
			in_list_view: 1,
			read_only: 1,
		},
		{
			fieldtype:"Check",
			fieldname:"is_alternative",
			label: __("Is Alternative"),
			read_only: 1,
		}];


		this.data = this.frm.doc.items.filter(
			(item) => item.is_alternative || item.has_alternative_item
		).map((item) => {
			return {
				"name": item.name,
				"item_code": item.item_code,
				"description": item.description,
				"amount": item.amount,
				"is_alternative": item.is_alternative,
			}
		});

		const dialog = new frappe.ui.Dialog({
			title: __("Select Alternative Items for Sales Order"),
			fields: [
				{
					fieldname: "info",
					fieldtype: "HTML",
					read_only: 1
				},
				{
					fieldname: "alternative_items",
					fieldtype: "Table",
					cannot_add_rows: true,
					cannot_delete_rows: true,
					in_place_edit: true,
					reqd: 1,
					data: this.data,
					description: __("Select an item from each set to be used in the Sales Order."),
					get_data: () => {
						return this.data;
					},
					fields: table_fields
				},
			],
			primary_action: function() {
				frappe.model.open_mapped_doc({
					method: "erpnext.selling.doctype.quotation.quotation.make_sales_order",
					frm: me.frm,
					args: {
						selected_items: dialog.fields_dict.alternative_items.grid.get_selected_children()
					}
				});
				dialog.hide();
			},
			primary_action_label: __('Continue')
		});

		dialog.fields_dict.info.$wrapper.html(
			`<p class="small text-muted">
				<span class="indicator yellow"></span>
				${__("Alternative Items")}
			</p>`
		)
		dialog.show();
	}
};

cur_frm.script_manager.make(erpnext.selling.QuotationController);

frappe.ui.form.on("Quotation Item", "items_on_form_rendered", "packed_items_on_form_rendered", function(frm, cdt, cdn) {
	// enable tax_amount field if Actual
})

frappe.ui.form.on("Quotation Item", "stock_balance", function(frm, cdt, cdn) {
	var d = frappe.model.get_doc(cdt, cdn);
	frappe.route_options = {"item_code": d.item_code};
	frappe.set_route("query-report", "Stock Balance");
})

frappe.ui.form.on('Quotation Item',{
    from_year: function(frm, cdt, cdn){
		let d = locals[cdt][cdn];
		if(d.from_year > 0 && d.to_year > 0 && d.from_year <= d.to_year) {
			d.qty = d.to_year - d.from_year + 1
		}else {
			d.qty = 0
		}
		d.amount = d.qty * d.rate
		frm.refresh_field('items');
		//summary
		var total = 0;
		var total_qty = 0;
		frm.doc.items.forEach(function (d) { 
			total += d.amount;
			total_qty += d.qty;
		});
		cur_frm.set_value('total', total);
		cur_frm.set_value('total_qty', total_qty);
		frm.refresh_field('total','total_qty');
	},
	to_year: function(frm, cdt, cdn){
		let d = locals[cdt][cdn];
		if(d.from_year > 0 && d.to_year > 0 && d.from_year <= d.to_year) {
			d.qty = d.to_year - d.from_year + 1
		}else {
			d.qty = 0
		}
		d.amount = d.qty * d.rate
		frm.refresh_field('items');
		//summary
		var total = 0;
		var total_qty = 0;
		frm.doc.items.forEach(function (d) { 
			total += d.amount;
			total_qty += d.qty;
		});
		cur_frm.set_value('total', total);
		cur_frm.set_value('total_qty', total_qty);
		frm.refresh_field('total','total_qty');
	},
	items_remove: function(frm, cdt, cdn){
		var d = locals[cdt][cdn];
		var total = 0;
		var total_qty = 0;
		frm.doc.items.forEach(function (d) { 
			total += d.amount;
			total_qty += d.qty;
		});
		cur_frm.set_value('total', total);
		cur_frm.set_value('total_qty', total_qty);
		refresh_field('total','total_qty');
	}
})
