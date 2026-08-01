package kind

import "testing"

func TestFillAccountBalanceLocalAmountsUsesBaseAmount(t *testing.T) {
	row := map[string]interface{}{
		"FDEBIT":      "12,345.67",
		"FDEBITLOCAL": nil,
		"FCREDIT":     8.5,
	}

	fillAccountBalanceLocalAmounts(row)

	if row["FDEBITLOCAL"] != "12,345.67" {
		t.Fatalf("FDEBITLOCAL = %#v, want base amount", row["FDEBITLOCAL"])
	}
	if _, exists := row["FCREDITLOCAL"]; !exists {
		t.Fatal("FCREDITLOCAL was not filled")
	}
}
