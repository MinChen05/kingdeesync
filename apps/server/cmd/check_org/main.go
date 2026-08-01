package main

import (
	"log"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/kind"
)

func main() {
	// 从当前工作目录加载配置（config.local.ini 不入库，见 .gitignore）
	if _, err := config.Load("config.local.ini"); err != nil {
		panic(err)
	}

	client := kind.NewKingdeeClient()
	if err := client.Login(); err != nil {
		panic(err)
	}

	// Query distinct orgs from material to see what FUSEORGID values exist
	params := kind.QueryParams{
		FormID:       "BD_MATERIAL",
		FieldKeys:    "FMATERIALID,FNUMBER,FUSEORGID,FNAME",
		Filter:       "FNUMBER = '100101010001'",
		StartRow:     0,
		Limit:        10,
		FieldKeyList: []string{"FMATERIALID", "FNUMBER", "FUSEORGID", "FNAME"},
	}

	result, err := client.QueryData(params)
	if err != nil {
		panic(err)
	}

	log.Printf("Material query returned %d rows", len(result.Rows))
}
