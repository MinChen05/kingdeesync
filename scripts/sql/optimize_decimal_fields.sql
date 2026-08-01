-- ========================================
-- 数据库字段精度优化脚本
-- 生成时间: 2026-05-07
-- 说明: 优化 decimal 字段精度，减少存储空间
-- ========================================

USE [your_database];
GO

-- 优化表: AP_Payable
PRINT '正在优化表 AP_Payable...';
ALTER TABLE [dbo].[AP_Payable] ALTER COLUMN [FPRICEQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[AP_Payable] ALTER COLUMN [FALLAMOUNTFOR_D] decimal(18,2) NULL;
ALTER TABLE [dbo].[AP_Payable] ALTER COLUMN [FNOTAXAMOUNTFOR] decimal(18,2) NULL;
ALTER TABLE [dbo].[AP_Payable] ALTER COLUMN [FDISCOUNTAMOUNTFOR] decimal(18,2) NULL;
ALTER TABLE [dbo].[AP_Payable] ALTER COLUMN [FENTRYDISCOUNTRATE] decimal(5,2) NULL;
ALTER TABLE [dbo].[AP_Payable] ALTER COLUMN [FENTRYTAXRATE] decimal(5,2) NULL;
GO

-- 优化表: AR_receivable
PRINT '正在优化表 AR_receivable...';
ALTER TABLE [dbo].[AR_receivable] ALTER COLUMN [FTAXPRICE] decimal(18,2) NULL;
ALTER TABLE [dbo].[AR_receivable] ALTER COLUMN [FPRICEQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[AR_receivable] ALTER COLUMN [FALLAMOUNTFOR_D] decimal(18,2) NULL;
GO

-- 优化表: bd_material
PRINT '正在优化表 bd_material...';
ALTER TABLE [dbo].[bd_material] ALTER COLUMN [F_JY_QTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[bd_material] ALTER COLUMN [F_JY_QTY1] decimal(18,4) NULL;
GO

-- 优化表: eng_bom
PRINT '正在优化表 eng_bom...';
ALTER TABLE [dbo].[eng_bom] ALTER COLUMN [FQTY] decimal(18,4) NULL;
GO

-- 优化表: eng_bomchild
PRINT '正在优化表 eng_bomchild...';
ALTER TABLE [dbo].[eng_bomchild] ALTER COLUMN [FNUMERATOR] decimal(18,4) NULL;
ALTER TABLE [dbo].[eng_bomchild] ALTER COLUMN [FDENOMINATOR] decimal(18,4) NULL;
ALTER TABLE [dbo].[eng_bomchild] ALTER COLUMN [FQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[eng_bomchild] ALTER COLUMN [FACTUALQTY] decimal(18,4) NULL;
GO

-- 优化表: GL_RPT_AccountBalance
PRINT '正在优化表 GL_RPT_AccountBalance...';
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FBEGINYEARDEBITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FBEGINYEARCREDITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FBEGINDEBIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FBEGINDEBITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FBEGINCREDIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FBEGINCREDITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FDEBIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FDEBITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FCREDIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FCREDITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FYTDDEBIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FYTDDEBITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FYTDCREDIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FYTDCREDITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FENDDEBIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FENDDEBITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FENDCREDIT] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FENDCREDITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FPROFITLOCAL] decimal(18,2) NULL;
ALTER TABLE [dbo].[GL_RPT_AccountBalance] ALTER COLUMN [FYTDPROFITLOCAL] decimal(18,2) NULL;
GO

-- 优化表: prd_ppbom
PRINT '正在优化表 prd_ppbom...';
ALTER TABLE [dbo].[prd_ppbom] ALTER COLUMN [FBASEQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[prd_ppbom] ALTER COLUMN [FQTY] decimal(18,4) NULL;
GO

-- 优化表: prd_ppbomentry
PRINT '正在优化表 prd_ppbomentry...';
ALTER TABLE [dbo].[prd_ppbomentry] ALTER COLUMN [FBASESTDQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[prd_ppbomentry] ALTER COLUMN [FBASENEEDQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[prd_ppbomentry] ALTER COLUMN [FBASEMUSTQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[prd_ppbomentry] ALTER COLUMN [FSTDQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[prd_ppbomentry] ALTER COLUMN [FNEEDQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[prd_ppbomentry] ALTER COLUMN [FMUSTQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[prd_ppbomentry] ALTER COLUMN [FBASEPICKEDQTY] decimal(18,4) NULL;
GO

-- 优化表: pur_purchaseorder
PRINT '正在优化表 pur_purchaseorder...';
ALTER TABLE [dbo].[pur_purchaseorder] ALTER COLUMN [FQTY] decimal(18,4) NULL;
GO

-- 优化表: saleorder
PRINT '正在优化表 saleorder...';
ALTER TABLE [dbo].[saleorder] ALTER COLUMN [FQTY] decimal(18,4) NULL;
ALTER TABLE [dbo].[saleorder] ALTER COLUMN [FStockOutQty] decimal(18,4) NULL;
GO

-- 优化表: STK_INVENTORY
PRINT '正在优化表 STK_INVENTORY...';
ALTER TABLE [dbo].[STK_INVENTORY] ALTER COLUMN [FBASEQTY] decimal(18,6) NULL;
GO

-- ========================================
-- 优化完成
-- ========================================
PRINT '所有字段优化完成！';
GO