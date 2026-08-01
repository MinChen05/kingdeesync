package db

import "testing"

func TestGetPrimaryKeyMatchesMSSQLBusinessKeyContract(t *testing.T) {
	want := map[string]string{
		"ap_payable": "FID,FENTRYID", "ar_receivable": "FID,FENTRYID", "bd_material": "FNUMBER",
		"bd_stock": "FSTOCKID", "customer": "FNUMBER", "eng_bom": "FID",
		"eng_bomchild": "FID,FENTRYID", "gl_rpt_accountbalance": "FBALANCEID", "pln_forecast": "FENTRYID",
		"prd_instock": "FID,FENTRYID", "prd_mo": "FID", "prd_moentry": "FID,FENTRYID",
		"prd_ppbom": "FID", "prd_ppbomentry": "FID,FENTRYID", "pur_purchaseorder": "FID,FENTRYID",
		"sal_deliverynotice": "FID,FENTRYID", "sal_outstock": "FENTRYID", "sal_returnstock": "FENTRYID",
		"saleorder": "FID,FENTRYID", "stk_instock": "FID,FENTRYID", "stk_inventory": "FID",
		"sub_subreqorder": "FID,FENTRYID",
	}
	for tableName, expected := range want {
		if got := GetPrimaryKey(tableName); got != expected {
			t.Errorf("GetPrimaryKey(%q) = %q, want %q", tableName, got, expected)
		}
	}
}
