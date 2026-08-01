-- ============================================================
-- Doris 表结构 DDL（按实际重建后结构生成）
-- 生成时间：2026-07-31
-- 注意：此为历史非分区基线，分区表请使用迁移脚本生成
-- ============================================================

-- 应付单 (ap_payable)
DROP TABLE IF EXISTS `ap_payable`;
CREATE TABLE `ap_payable` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FBILLNAME                      varchar(256)              NULL,
    FBillNo                        varchar(128)              NULL,
    FDATE                          datetimev2(0)             NULL,
    FPURCHASEORGNAME               varchar(128)              NULL,
    FCUSTOMER                      varchar(256)              NULL,
    FSUPPLIERNAME                  varchar(256)              NULL,
    FSETACCOUNTTYPE                int                       NULL,
    FMATERIALNUMBER                varchar(128)              NULL,
    FMATERIALNAME                  varchar(256)              NULL,
    FPRICEUNITNAME                 varchar(64)               NULL,
    FPRICEQTY                      decimalv3(18,4)           NULL,
    FALLAMOUNTFOR_D                decimalv3(18,4)           NULL,
    FNoTaxAmountFor_D              decimalv3(18,4)           NULL,
    FDISCOUNTAMOUNTFOR             decimalv3(18,4)           NULL,
    FENTRYDISCOUNTRATE             decimalv3(18,4)           NULL,
    FENTRYTAXRATE                  decimalv3(18,4)           NULL,
    FModifyDate                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '应付单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 应收单 (ar_receivable)
DROP TABLE IF EXISTS `ar_receivable`;
CREATE TABLE `ar_receivable` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FBILLNAME                      varchar(256)              NULL,
    FBillNo                        varchar(128)              NULL,
    FDATE                          datetimev2(0)             NULL,
    FCUSTOMERNAME                  varchar(256)              NULL,
    FSETACCOUNTTYPE                int                       NULL,
    FBASEPROPERTY1                 varchar(128)              NULL,
    FSOURCEBILLNO                  varchar(128)              NULL,
    FMATERIALNUMBER                varchar(128)              NULL,
    FMATERIALNAME                  varchar(256)              NULL,
    FTAXPRICE                      decimalv3(18,4)           NULL,
    FPRICEQTY                      decimalv3(18,4)           NULL,
    FALLAMOUNTFOR_D                decimalv3(18,4)           NULL,
    FModifyDate                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '应收单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 物料 (bd_material)
DROP TABLE IF EXISTS `bd_material`;
CREATE TABLE `bd_material` (

    FNUMBER                        varchar(500)              NOT NULL,
    FMATERIALID                    bigint                    NULL,
    FMASTERID                      bigint                    NULL,
    FMATERIALGROUP                 varchar(500)              NULL,
    FCREATEORGID                   bigint                    NULL,
    FUSEORGID                      bigint                    NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    FFORBIDSTATUS                  varchar(32)               NULL,
    FCREATEDATE                    datetimev2(0)             NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    FAPPROVEDATE                   datetimev2(0)             NULL,
    FREFSTATUS                     varchar(500)              NULL,
    F_TMHE_TEXT                    varchar(500)              NULL,
    F_JY_TEXT                      varchar(500)              NULL,
    F_JY_TEXT1                     varchar(500)              NULL,
    F_JY_TEXT2                     varchar(500)              NULL,
    F_JYX_TEXT1                    varchar(500)              NULL,
    F_JYX_TEXT2                    varchar(500)              NULL,
    F_JYX_TEXT4                    varchar(500)              NULL,
    F_JYX_TEXT3                    varchar(500)              NULL,
    F_JYX_ASSISTANT                varchar(500)              NULL,
    F_JYX_ASSISTANT1               varchar(500)              NULL,
    F_JYX_ASSISTANT2               varchar(500)              NULL,
    F_JY_QTY                       decimalv3(18,6)           NULL,
    F_JY_QTY1                      decimalv3(18,6)           NULL,
    F_KDKF_HJFS                    varchar(500)              NULL,
    F_ora_Text_9sb                 varchar(500)              NULL,
    F_ORA_TEXT_QTR                 varchar(500)              NULL,
    F_ORA_TEXT_QTR1                varchar(500)              NULL,
    FERPCLSID                      varchar(500)              NULL,
    FCATEGORYID                    bigint                    NULL,
    FTYPEID                        bigint                    NULL,
    FBARCODE                       varchar(500)              NULL,
    FNAME                          varchar(500)              NULL,
    FSPECIFICATION                 varchar(500)              NULL,
    FDescription                   varchar(500)              NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FNUMBER)
COMMENT '物料'
DISTRIBUTED BY HASH(FNUMBER)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 仓库 (bd_stock)
DROP TABLE IF EXISTS `bd_stock`;
CREATE TABLE `bd_stock` (

    FSTOCKID                       bigint                    NOT NULL,
    FMASTERID                      bigint                    NULL,
    FNUMBER                        varchar(128)              NULL,
    FUSEORGID                      bigint                    NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    FFORBIDSTATUS                  varchar(32)               NULL,
    FNAME                          varchar(256)              NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FSTOCKID)
COMMENT '仓库'
DISTRIBUTED BY HASH(FSTOCKID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 客户资料 (customer)
DROP TABLE IF EXISTS `customer`;
CREATE TABLE `customer` (

    FNUMBER                        varchar(500)              NOT NULL,
    FCUSTID                        varchar(500)              NULL,
    FNAME                          varchar(500)              NULL,
    FGROUP                         varchar(500)              NULL,
    FSELLERNAME                    varchar(500)              NULL,
    FSTAFF                         varchar(500)              NULL,
    FCUSTLEVEL                     varchar(500)              NULL,
    FCUSTPYPE                      varchar(500)              NULL,
    FCREATEDATE                    datetimev2(0)             NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FNUMBER)
COMMENT '客户资料'
DISTRIBUTED BY HASH(FNUMBER)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 物料清单 (eng_bom)
DROP TABLE IF EXISTS `eng_bom`;
CREATE TABLE `eng_bom` (

    FID                            bigint                    NOT NULL,
    FMASTERID                      bigint                    NULL,
    FNUMBER                        varchar(128)              NULL,
    FBILLTYPE                      varchar(128)              NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    FMATERIALID                    bigint                    NULL,
    FFORBIDSTATUS                  varchar(32)               NULL,
    FUSEORGID                      bigint                    NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    FBASEUNITID                    bigint                    NULL,
    FQTY                           decimalv3(18,4)           NULL,
    FBOMUSE                        bigint                    NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID)
COMMENT '物料清单'
DISTRIBUTED BY HASH(FID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 物料清单子项 (eng_bomchild)
DROP TABLE IF EXISTS `eng_bomchild`;
CREATE TABLE `eng_bomchild` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FMATERIALID                    bigint                    NULL,
    FCHILDNUMBER                   varchar(128)              NULL,
    FCHILDNAME                     varchar(256)              NULL,
    FNUMERATOR                     decimalv3(18,4)           NULL,
    FDENOMINATOR                   decimalv3(18,4)           NULL,
    FISSUETYPE                     varchar(64)               NULL,
    FBACKFLUSHTYPE                 varchar(64)               NULL,
    FSUPPLYORG                     bigint                    NULL,
    FSTOCKID                       bigint                    NULL,
    FENTRYROWID                    varchar(128)              NULL,
    FREPLACEGROUP                  bigint                    NULL,
    FQTY                           decimalv3(18,4)           NULL,
    FACTUALQTY                     decimalv3(18,4)           NULL,
    FMASTERID                      bigint                    NULL,
    FMATERIALTYPE                  varchar(500)              NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '物料清单子项'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 科目余额表 (gl_rpt_accountbalance)
DROP TABLE IF EXISTS `gl_rpt_accountbalance`;
CREATE TABLE `gl_rpt_accountbalance` (

    FACCTYEAR                      int                       NOT NULL,
    FACCTPERIOD                    int                       NULL,
    FBALANCEID                     varchar(80)               NULL,
    FBALANCENAME                   varchar(256)              NULL,
    FDETAILNUMBER                  varchar(128)              NULL,
    FDETAILNAME                    varchar(256)              NULL,
    FBEGINYEARDEBITLOCAL           decimalv3(18,4)           NULL,
    FBEGINYEARCREDITLOCAL          decimalv3(18,4)           NULL,
    FBEGINDEBIT                    decimalv3(18,4)           NULL,
    FBEGINDEBITLOCAL               decimalv3(18,4)           NULL,
    FBEGINCREDIT                   decimalv3(18,4)           NULL,
    FBEGINCREDITLOCAL              decimalv3(18,4)           NULL,
    FDEBIT                         decimalv3(18,4)           NULL,
    FDEBITLOCAL                    decimalv3(18,4)           NULL,
    FCREDIT                        decimalv3(18,4)           NULL,
    FCREDITLOCAL                   decimalv3(18,4)           NULL,
    FYTDDEBIT                      decimalv3(18,4)           NULL,
    FYTDDEBITLOCAL                 decimalv3(18,4)           NULL,
    FYTDCREDIT                     decimalv3(18,4)           NULL,
    FYTDCREDITLOCAL                decimalv3(18,4)           NULL,
    FENDDEBIT                      decimalv3(18,4)           NULL,
    FENDDEBITLOCAL                 decimalv3(18,4)           NULL,
    FENDCREDIT                     decimalv3(18,4)           NULL,
    FENDCREDITLOCAL                decimalv3(18,4)           NULL,
    FPROFITLOCAL                   decimalv3(18,4)           NULL,
    FYTDPROFITLOCAL                decimalv3(18,4)           NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
DUPLICATE KEY(FACCTYEAR)
COMMENT '科目余额表'
DISTRIBUTED BY HASH(FACCTYEAR)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 预测订单 (pln_forecast)
DROP TABLE IF EXISTS `pln_forecast`;
CREATE TABLE `pln_forecast` (

    FENTRYID                       bigint                    NOT NULL,
    FBillNo                        varchar(128)              NULL,
    FFOREORGNAME                   varchar(500)              NULL,
    FCUSTNAME                      varchar(500)              NULL,
    FCUSTGROUP                     varchar(500)              NULL,
    FMATERIALNAME                  varchar(256)              NULL,
    FMATERIALNUMBER                varchar(128)              NULL,
    FQty                           decimalv3(18,4)           NULL,
    FORA_BASE_FNAME                varchar(500)              NULL,
    FORA_BASEPROPERTY_CA9          varchar(500)              NULL,
    FORA_BASEPROPERTY_UKY          varchar(500)              NULL,
    F_ora_Date                     datetimev2(0)             NULL,
    FModifyDate                    datetimev2(0)             NULL,
    FDESCRIPTION                   varchar(510)              NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FENTRYID)
COMMENT '预测订单'
DISTRIBUTED BY HASH(FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 生产入库单 (prd_instock)
DROP TABLE IF EXISTS `prd_instock`;
CREATE TABLE `prd_instock` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FBILLNO                        varchar(128)              NULL,
    FDATE                          datetimev2(0)             NULL,
    FMATERIALID                    bigint                    NULL,
    FREALQTY                       decimalv3(18,4)           NULL,
    FSrcEntrySeq                   int                       NULL,
    FSRCBILLNO                     varchar(128)              NULL,
    FMoEntrySeq                    int                       NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    FMoBillNo                      varchar(128)              NULL,
    FModifyDate                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '生产入库单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 生产订单主表 (prd_mo)
DROP TABLE IF EXISTS `prd_mo`;
CREATE TABLE `prd_mo` (

    FID                            bigint                    NOT NULL,
    FBILLNO                        varchar(128)              NULL,
    FBILLTYPE                      varchar(128)              NULL,
    FDATE                          datetimev2(0)             NULL,
    FPRDORGID                      bigint                    NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    FCREATEDATE                    datetimev2(0)             NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    FCANCELSTATUS                  varchar(32)               NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID)
COMMENT '生产订单主表'
DISTRIBUTED BY HASH(FID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 生产订单明细 (prd_moentry)
DROP TABLE IF EXISTS `prd_moentry`;
CREATE TABLE `prd_moentry` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FSrcBillNo                     varchar(128)              NULL,
    FSRCBILLENTRYID                bigint                    NULL,
    FSALEORDERNO                   varchar(128)              NULL,
    FMATERIALID                    bigint                    NULL,
    FQTY                           decimalv3(18,4)           NULL,
    FSTOCKINQUAAUXQTY              decimalv3(18,4)           NULL,
    FPLANSTARTDATE                 datetimev2(0)             NULL,
    FPLANFINISHDATE                datetimev2(0)             NULL,
    FBOMID                         bigint                    NULL,
    FREQUESTORGID                  bigint                    NULL,
    FSTOCKINORGID                  bigint                    NULL,
    FSTOCKID                       bigint                    NULL,
    FWORKSHOPID                    bigint                    NULL,
    FSTATUS                        varchar(256)              NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    F_ora_Text1                    varchar(256)              NULL,
    FMATERIALNUMBER                varchar(128)              NULL,
    FDESCRIPTION                   varchar(510)              NULL,
    FSRCBILLENTRYSEQ               int                       NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '生产订单明细'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 生产用料清单主表 (prd_ppbom)
DROP TABLE IF EXISTS `prd_ppbom`;
CREATE TABLE `prd_ppbom` (

    FID                            bigint                    NOT NULL,
    FBILLNO                        varchar(128)              NULL,
    FMATERIALID                    bigint                    NULL,
    FPRDORGID                      bigint                    NULL,
    FWORKSHOPID                    bigint                    NULL,
    FBOMID                         bigint                    NULL,
    FBASEQTY                       decimalv3(18,6)           NULL,
    FQTY                           decimalv3(18,4)           NULL,
    FMOTYPE                        varchar(64)               NULL,
    FMOID                          varchar(128)              NULL,
    FMOBILLNO                      varchar(128)              NULL,
    FMOENTRYID                     varchar(128)              NULL,
    FMOENTRYSEQ                    int                       NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    FCREATEDATE                    datetimev2(0)             NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    FAPPROVEDATE                   datetimev2(0)             NULL,
    FSALEORDERID                   bigint                    NULL,
    FSALEORDERNO                   varchar(128)              NULL,
    FSALEORDERENTRYID              bigint                    NULL,
    FSALEORDERENTRYSEQ             int                       NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID)
COMMENT '生产用料清单主表'
DISTRIBUTED BY HASH(FID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 生产用料清单明细表 (prd_ppbomentry)
DROP TABLE IF EXISTS `prd_ppbomentry`;
CREATE TABLE `prd_ppbomentry` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FMOID                          varchar(128)              NULL,
    FMOBILLNO                      varchar(128)              NULL,
    FMOENTRYID                     varchar(128)              NULL,
    FMOENTRYSEQ                    int                       NULL,
    FBOMENTRYID                    varchar(128)              NULL,
    FMATERIALID                    bigint                    NULL,
    FNEEDDATE                      datetimev2(0)             NULL,
    FBASESTDQTY                    decimalv3(18,4)           NULL,
    FBASENEEDQTY                   decimalv3(18,4)           NULL,
    FBASEMUSTQTY                   decimalv3(18,4)           NULL,
    FSTDQTY                        decimalv3(18,4)           NULL,
    FNEEDQTY                       decimalv3(18,4)           NULL,
    FMUSTQTY                       decimalv3(18,4)           NULL,
    FBASEPICKEDQTY                 decimalv3(18,4)           NULL,
    FPLANEND                       datetimev2(0)             NULL,
    FMODIFYDATE                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '生产用料清单明细表'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 采购订单 (pur_purchaseorder)
DROP TABLE IF EXISTS `pur_purchaseorder`;
CREATE TABLE `pur_purchaseorder` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FBillNo                        varchar(128)              NULL,
    FDocumentStatus                varchar(32)               NULL,
    FSupplier                      varchar(256)              NULL,
    FPurchaseDept                  varchar(128)              NULL,
    F_ora_Assistant                varchar(128)              NULL,
    FNUMBER                        varchar(128)              NULL,
    FNAME                          varchar(256)              NULL,
    FSpecification                 varchar(500)              NULL,
    FQTY                           decimalv3(18,4)           NULL,
    FCreateDate                    datetimev2(0)             NULL,
    FModifyDate                    datetimev2(0)             NULL,
    FApproveDate                   datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '采购订单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 发货通知单 (sal_deliverynotice)
DROP TABLE IF EXISTS `sal_deliverynotice`;
CREATE TABLE `sal_deliverynotice` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FBillNo                        varchar(128)              NULL,
    FDate                          datetimev2(0)             NULL,
    FCUSTNAME                      varchar(500)              NULL,
    FMaterialNAME                  varchar(256)              NULL,
    FMaterialNUMBER                varchar(128)              NULL,
    FQTY                           decimalv3(18,4)           NULL,
    FSumOutQty                     decimalv3(23,4)           NULL,
    FCLOSESTATUS_MX                varchar(500)              NULL,
    FModifyDate                    datetimev2(0)             NULL,
    FSrcBillNo                     varchar(128)              NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '发货通知单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 销售出库单 (sal_outstock)
DROP TABLE IF EXISTS `sal_outstock`;
CREATE TABLE `sal_outstock` (

    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FBILLTYPENAME                  varchar(500)              NULL,
    FBillNO                        varchar(128)              NULL,
    FDate                          datetimev2(0)             NULL,
    FCUSTNAME                      varchar(500)              NULL,
    FSALEORGNAME                   varchar(500)              NULL,
    FCUSTGROUP                     varchar(500)              NULL,
    FRealQty                       decimalv3(18,4)           NULL,
    FMATERIALNAME                  varchar(256)              NULL,
    FMATERIALNUMBER                varchar(128)              NULL,
    FMATERIALTYPE                  varchar(500)              NULL,
    FMATERIALSORT                  varchar(500)              NULL,
    FSRCBILLNO                     varchar(128)              NULL,
    FModifyDate                    datetimev2(0)             NULL,
    FDESCRIPTION                   varchar(510)              NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FENTRYID)
COMMENT '销售出库单'
DISTRIBUTED BY HASH(FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 销售退货单 (sal_returnstock)
DROP TABLE IF EXISTS `sal_returnstock`;
CREATE TABLE `sal_returnstock` (

    FENTRYID                       bigint                    NOT NULL,
    FBillNo                        varchar(128)              NULL,
    FDATE                          datetimev2(0)             NULL,
    FRetcustNAME                   varchar(500)              NULL,
    FRetcustGROUP                  varchar(500)              NULL,
    FSalesManNAME                  varchar(500)              NULL,
    FReturnType                    varchar(500)              NULL,
    FRealQty                       decimalv3(18,4)           NULL,
    FMaterialNAME                  varchar(256)              NULL,
    FMaterialFNUMBER               varchar(500)              NULL,
    FMaterialTYPE                  varchar(500)              NULL,
    FMaterialSort                  varchar(500)              NULL,
    FDeliveryDate                  datetimev2(0)             NULL,
    FModifyDate                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FENTRYID)
COMMENT '销售退货单'
DISTRIBUTED BY HASH(FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 销售订单 (saleorder)
DROP TABLE IF EXISTS `saleorder`;
CREATE TABLE `saleorder` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FBILLTYPENAME                  varchar(500)              NULL,
    FBillNo                        varchar(128)              NULL,
    FDate                          datetimev2(0)             NULL,
    FCUSTNAME                      varchar(500)              NULL,
    FSALEORONAME                   varchar(500)              NULL,
    FCUSTGROUP                     varchar(500)              NULL,
    FMaterialId                    bigint                    NULL,
    FMATERIALNAME                  varchar(256)              NULL,
    FMATERIALNUMBER                varchar(128)              NULL,
    FMATERIALTYPE                  varchar(500)              NULL,
    FMATERIALSORT                  varchar(500)              NULL,
    FDESCRIPTION                   varchar(510)              NULL,
    FQTY                           decimalv3(18,4)           NULL,
    FCloseStatus                   varchar(500)              NULL,
    FDeliveryDate                  datetimev2(0)             NULL,
    FModifyDate                    datetimev2(0)             NULL,
    FStockOutQty                   decimalv3(18,4)           NULL,
    FMrpCloseStatus                varchar(500)              NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '销售订单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 采购入库单 (stk_instock)
DROP TABLE IF EXISTS `stk_instock`;
CREATE TABLE `stk_instock` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSEQ                           int                       NULL,
    FBillNo                        varchar(128)              NULL,
    FDate                          datetimev2(0)             NULL,
    FDocumentStatus                varchar(32)               NULL,
    FSUPPLIERNAME                  varchar(256)              NULL,
    FPURCHASEORGNAME               varchar(128)              NULL,
    FMATERIALNUMBER                varchar(128)              NULL,
    FMATERIALNAME                  varchar(256)              NULL,
    FRealQty                       decimalv3(18,4)           NULL,
    FSrcBillNo                     varchar(128)              NULL,
    FSRCENTRYSEQ                   int                       NULL,
    FModifyDate                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '采购入库单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 即时库存 (stk_inventory)
DROP TABLE IF EXISTS `stk_inventory`;
CREATE TABLE `stk_inventory` (

    FID                            bigint                    NOT NULL,
    FSTOCKORGID                    bigint                    NULL,
    FSTOCKID                       bigint                    NULL,
    FSTOCKLOCID                    bigint                    NULL,
    FSTOCKSTATUSID                 bigint                    NULL,
    FBASEUNITID                    bigint                    NULL,
    FBASEQTY                       decimalv3(18,6)           NULL,
    FMATERIALID                    bigint                    NULL,
    FUPDATETIME                    datetimev2(0)             NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID)
COMMENT '即时库存'
DISTRIBUTED BY HASH(FID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');

-- 委外订单 (sub_subreqorder)
DROP TABLE IF EXISTS `sub_subreqorder`;
CREATE TABLE `sub_subreqorder` (

    FID                            bigint                    NOT NULL,
    FENTRYID                       bigint                    NOT NULL,
    FSrcBillNO                     varchar(128)              NULL,
    FSRCBILLENTRYSEQ               int                       NULL,
    FSRCBILLENTRYID                bigint                    NULL,
    FSrcBillId                     bigint                    NULL,
    FBillTypeNAME                  varchar(500)              NULL,
    FBillNo                        varchar(128)              NULL,
    FDATE                          datetimev2(0)             NULL,
    FCustomer                      varchar(256)              NULL,
    FNUMBER                        varchar(128)              NULL,
    FQty                           decimalv3(18,4)           NULL,
    FStockInQty                    decimalv3(18,4)           NULL,
    FSupplier                      varchar(256)              NULL,
    FModifyDate                    datetimev2(0)             NULL,
    FDOCUMENTSTATUS                varchar(32)               NULL,
    FDESCRIPTION                   varchar(510)              NULL,
    SYNC_TIME                      datetimev2(0)             NULL
)
UNIQUE KEY(FID,FENTRYID)
COMMENT '委外订单'
DISTRIBUTED BY HASH(FID,FENTRYID)
PROPERTIES ('replication_allocation' = 'tag.location.default: 1');
