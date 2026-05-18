-- 帆软正式查询修正版
-- 说明：
-- 1) 从客户销量汇总起步，避免遗漏“有销量但无收入”的客户
-- 2) 所有日期字段使用 TRY_CONVERT，避免 241
-- 3) 物流费用改取不含税金额字段

;WITH 月费率 AS (
    SELECT
        YEAR(TRY_CONVERT(DATE, FDATE)) * 12 + MONTH(TRY_CONVERT(DATE, FDATE)) AS 年月,
        CASE
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 500000 THEN 0.0578
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 550000 THEN 0.0551
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 600000 THEN 0.0525
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 650000 THEN 0.0499
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 700000 THEN 0.0473
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 750000 THEN 0.0446
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 800000 THEN 0.0420
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 850000 THEN 0.0394
            WHEN SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) <= 940000 THEN 0.0368
            ELSE 0.0341
        END AS 费率值
    FROM AR_Receivable
    WHERE LTRIM(RTRIM(CAST(FSETACCOUNTTYPE AS NVARCHAR(20)))) = '3'
      AND FMATERIALNAME = N'电机'
      AND (FBASEPROPERTY1 <> 'True' OR FBASEPROPERTY1 IS NULL)
      AND FCUSTOMERNAME IS NOT NULL
      AND RTRIM(LTRIM(FCUSTOMERNAME)) <> ''
      ${if(len(START) == 0, "", "AND TRY_CONVERT(DATE, FDATE) >= CONVERT(DATE, '" + START + "-01', 23)")}
      ${if(len(END) == 0, "", "AND TRY_CONVERT(DATE, FDATE) < DATEADD(MONTH, 1, CONVERT(DATE, '" + END + "-01', 23))")}
    GROUP BY YEAR(TRY_CONVERT(DATE, FDATE)) * 12 + MONTH(TRY_CONVERT(DATE, FDATE))
),
客户月管理费用 AS (
    SELECT
        RTRIM(LTRIM(r.FCUSTOMERNAME)) AS FCUSTOMERNAME,
        SUM(r.月销量 * f.费率值) AS 管理费用
    FROM (
        SELECT
            FCUSTOMERNAME,
            YEAR(TRY_CONVERT(DATE, FDATE)) * 12 + MONTH(TRY_CONVERT(DATE, FDATE)) AS 年月,
            SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) AS 月销量
        FROM AR_Receivable
        WHERE LTRIM(RTRIM(CAST(FSETACCOUNTTYPE AS NVARCHAR(20)))) = '3'
          AND FMATERIALNAME = N'电机'
          AND (FBASEPROPERTY1 <> 'True' OR FBASEPROPERTY1 IS NULL)
          AND FCUSTOMERNAME IS NOT NULL
          AND RTRIM(LTRIM(FCUSTOMERNAME)) <> ''
          ${if(len(START) == 0, "", "AND TRY_CONVERT(DATE, FDATE) >= CONVERT(DATE, '" + START + "-01', 23)")}
          ${if(len(END) == 0, "", "AND TRY_CONVERT(DATE, FDATE) < DATEADD(MONTH, 1, CONVERT(DATE, '" + END + "-01', 23))")}
          ${if(len(客户) == 0, "", "AND RTRIM(LTRIM(FCUSTOMERNAME)) = N'" + 客户 + "'")}
        GROUP BY FCUSTOMERNAME, YEAR(TRY_CONVERT(DATE, FDATE)) * 12 + MONTH(TRY_CONVERT(DATE, FDATE))
    ) r
    JOIN 月费率 f
        ON r.年月 = f.年月
    GROUP BY RTRIM(LTRIM(r.FCUSTOMERNAME))
),
价税合计明细 AS (
    SELECT
        RTRIM(LTRIM(FDETAILNAME)) AS 客户名称,
        SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FCREDIT), 0)) AS 贷方金额
    FROM GL_RPT_AccountBalance
    WHERE FBALANCEID IN ('6001.01.01', '6001.01.05', '6001.05.01')
      ${if(len(START) == 0, "", "AND (COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTYEAR AS NVARCHAR(10))))), 0) * 100 + COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTPERIOD AS NVARCHAR(10))))), 0)) >= (CAST(LEFT('" + START + "', 4) AS INT) * 100 + CAST(RIGHT('" + START + "', 2) AS INT))")}
      ${if(len(END) == 0, "", "AND (COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTYEAR AS NVARCHAR(10))))), 0) * 100 + COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTPERIOD AS NVARCHAR(10))))), 0)) <= (CAST(LEFT('" + END + "', 4) AS INT) * 100 + CAST(RIGHT('" + END + "', 2) AS INT))")}
      AND FDETAILNAME IS NOT NULL
      AND RTRIM(LTRIM(FDETAILNAME)) <> ''
      ${if(len(客户) == 0, "", "AND RTRIM(LTRIM(FDETAILNAME)) LIKE N'%" + 客户 + "%'")}
    GROUP BY RTRIM(LTRIM(FDETAILNAME))
),
客户罚款明细 AS (
    SELECT
        RTRIM(LTRIM(
            CASE
                WHEN CHARINDEX('/', FDETAILNAME) > 0
                THEN LEFT(FDETAILNAME, CHARINDEX('/', FDETAILNAME) - 1)
                ELSE FDETAILNAME
            END
        )) AS 客户名称,
        SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FDEBIT), 0)) AS 借方金额
    FROM GL_RPT_AccountBalance
    WHERE FBALANCEID = '6711.04'
      ${if(len(START) == 0, "", "AND (COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTYEAR AS NVARCHAR(10))))), 0) * 100 + COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTPERIOD AS NVARCHAR(10))))), 0)) >= (CAST(LEFT('" + START + "', 4) AS INT) * 100 + CAST(RIGHT('" + START + "', 2) AS INT))")}
      ${if(len(END) == 0, "", "AND (COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTYEAR AS NVARCHAR(10))))), 0) * 100 + COALESCE(TRY_CONVERT(INT, LTRIM(RTRIM(CAST(FACCTPERIOD AS NVARCHAR(10))))), 0)) <= (CAST(LEFT('" + END + "', 4) AS INT) * 100 + CAST(RIGHT('" + END + "', 2) AS INT))")}
      AND FDETAILNAME IS NOT NULL
      AND RTRIM(LTRIM(FDETAILNAME)) <> ''
      ${if(len(客户) == 0, "", "AND RTRIM(LTRIM(FDETAILNAME)) LIKE N'%" + 客户 + "%'")}
    GROUP BY RTRIM(LTRIM(
        CASE
            WHEN CHARINDEX('/', FDETAILNAME) > 0
            THEN LEFT(FDETAILNAME, CHARINDEX('/', FDETAILNAME) - 1)
            ELSE FDETAILNAME
        END
    ))
),
客户基础资料 AS (
    SELECT
        RTRIM(LTRIM(FNAME)) AS FNAME,
        MAX(FNUMBER) AS FNUMBER,
        MAX(FSELLERNAME) AS FSELLERNAME,
        MAX(FCUSTPYPE) AS FCUSTPYPE
    FROM Customer
    WHERE FNAME IS NOT NULL
      AND RTRIM(LTRIM(FNAME)) <> ''
    GROUP BY RTRIM(LTRIM(FNAME))
),
客户销量汇总 AS (
    SELECT
        RTRIM(LTRIM(FCUSTOMERNAME)) AS 客户名称,
        SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), FPRICEQTY), 0)) AS 销量
    FROM AR_Receivable
    WHERE LTRIM(RTRIM(CAST(FSETACCOUNTTYPE AS NVARCHAR(20)))) = '3'
      AND FMATERIALNAME = N'电机'
      AND (FBASEPROPERTY1 <> 'True' OR FBASEPROPERTY1 IS NULL)
      AND FCUSTOMERNAME IS NOT NULL
      AND RTRIM(LTRIM(FCUSTOMERNAME)) <> ''
      ${if(len(START) == 0, "", "AND TRY_CONVERT(DATE, FDATE) >= CONVERT(DATE, '" + START + "-01', 23)")}
      ${if(len(END) == 0, "", "AND TRY_CONVERT(DATE, FDATE) < DATEADD(MONTH, 1, CONVERT(DATE, '" + END + "-01', 23))")}
      ${if(len(客户) == 0, "", "AND RTRIM(LTRIM(FCUSTOMERNAME)) = N'" + 客户 + "'")}
    GROUP BY RTRIM(LTRIM(FCUSTOMERNAME))
),
客户成本汇总 AS (
    SELECT
        RTRIM(LTRIM(customer)) AS 客户名称,
        SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), cost_amount), 0)) AS 成本金额
    FROM customer_cost_report
    WHERE RTRIM(LTRIM(COALESCE(customer, ''))) <> ''
      ${if(len(START) == 0, "", "AND COALESCE(LEFT(CONVERT(NVARCHAR(10), TRY_CONVERT(DATE, biz_date), 23), 7), LEFT(LTRIM(RTRIM(CAST(biz_date AS NVARCHAR(20)))), 7)) >= '" + START + "'")}
      ${if(len(END) == 0, "", "AND COALESCE(LEFT(CONVERT(NVARCHAR(10), TRY_CONVERT(DATE, biz_date), 23), 7), LEFT(LTRIM(RTRIM(CAST(biz_date AS NVARCHAR(20)))), 7)) <= '" + END + "'")}
      ${if(len(客户) == 0, "", "AND RTRIM(LTRIM(customer)) = N'" + 客户 + "'")}
    GROUP BY RTRIM(LTRIM(customer))
),
客户集合 AS (
    SELECT 客户名称 FROM 客户销量汇总
    UNION
    SELECT 客户名称 FROM 价税合计明细
    UNION
    SELECT 客户名称 FROM 客户罚款明细
    UNION
    SELECT 客户名称 FROM (
        SELECT COALESCE(NULLIF(RTRIM(LTRIM(p.FCUSTOMER)), ''), N'[未维护客户]') AS 客户名称
        FROM AP_Payable p
        WHERE p.FMATERIALNAME = '交通运输费'
          AND LTRIM(RTRIM(CAST(p.FSETACCOUNTTYPE AS NVARCHAR(20)))) = '3'
          ${if(len(START) == 0, "", "AND TRY_CONVERT(DATE, p.FDATE) >= CONVERT(DATE, '" + START + "-01', 23)")}
          ${if(len(END) == 0, "", "AND TRY_CONVERT(DATE, p.FDATE) < DATEADD(MONTH, 1, CONVERT(DATE, '" + END + "-01', 23))")}
          ${if(len(客户) == 0, "", "AND COALESCE(NULLIF(RTRIM(LTRIM(p.FCUSTOMER)), ''), N'[未维护客户]') = N'" + 客户 + "'")}
        GROUP BY COALESCE(NULLIF(RTRIM(LTRIM(p.FCUSTOMER)), ''), N'[未维护客户]')
    ) apx
    UNION
    SELECT 客户名称 FROM (
        SELECT RTRIM(LTRIM(s.FRetcustNAME)) AS 客户名称
        FROM sal_returnstock s
        WHERE s.FRetcustNAME IS NOT NULL
          AND RTRIM(LTRIM(s.FRetcustNAME)) <> ''
          ${if(len(START) == 0, "", "AND TRY_CONVERT(DATE, s.FDate) >= CONVERT(DATE, '" + START + "-01', 23)")}
          ${if(len(END) == 0, "", "AND TRY_CONVERT(DATE, s.FDate) < DATEADD(MONTH, 1, CONVERT(DATE, '" + END + "-01', 23))")}
          ${if(len(客户) == 0, "", "AND RTRIM(LTRIM(s.FRetcustNAME)) = N'" + 客户 + "'")}
        GROUP BY RTRIM(LTRIM(s.FRetcustNAME))
    ) retx
    UNION
    SELECT 客户名称 FROM 客户成本汇总
)
SELECT
    ROW_NUMBER() OVER (ORDER BY base.客户名称) AS 序号,
    base.客户名称 AS 客户,
    c.FNUMBER AS 客户编码,
    c.FSELLERNAME AS 业务员,
    c.FCUSTPYPE AS 客户类别,
    ISNULL(r.销量, 0) AS 销量,
    ISNULL(ap.物流费用, 0) AS 物流费用,
    ISNULL(ret.退货费用, 0) AS 退货费用,
    ISNULL(cm.管理费用, 0) AS 管理费用,
    CAST(0 AS DECIMAL(18, 2)) AS 返利费用,
    CAST(ROUND(ISNULL(p.贷方金额, 0), 4) AS DECIMAL(18, 2)) AS 价税合计,
    CAST(ROUND(ISNULL(s2.借方金额, 0), 4) AS DECIMAL(18, 2)) AS 客户罚款,
    CAST(ROUND(ISNULL(cb.成本金额, 0), 4) AS DECIMAL(18, 2)) AS 成本金额
FROM 客户集合 base
LEFT JOIN 客户基础资料 c
    ON base.客户名称 = c.FNAME
LEFT JOIN 客户销量汇总 r
    ON base.客户名称 = r.客户名称
LEFT JOIN 价税合计明细 p
    ON base.客户名称 = p.客户名称
LEFT JOIN (
    SELECT
        COALESCE(NULLIF(RTRIM(LTRIM(p.FCUSTOMER)), ''), N'[未维护客户]') AS FCUSTOMER,
        ROUND(SUM(COALESCE(TRY_CONVERT(DECIMAL(18, 4), p.FNOTAXAMOUNTFOR), 0)), 2) AS 物流费用
    FROM AP_Payable p
    WHERE p.FMATERIALNAME = '交通运输费'
      AND LTRIM(RTRIM(CAST(p.FSETACCOUNTTYPE AS NVARCHAR(20)))) = '3'
      ${if(len(START) == 0, "", "AND TRY_CONVERT(DATE, p.FDATE) >= CONVERT(DATE, '" + START + "-01', 23)")}
      ${if(len(END) == 0, "", "AND TRY_CONVERT(DATE, p.FDATE) < DATEADD(MONTH, 1, CONVERT(DATE, '" + END + "-01', 23))")}
      ${if(len(客户) == 0, "", "AND COALESCE(NULLIF(RTRIM(LTRIM(p.FCUSTOMER)), ''), N'[未维护客户]') = N'" + 客户 + "'")}
    GROUP BY COALESCE(NULLIF(RTRIM(LTRIM(p.FCUSTOMER)), ''), N'[未维护客户]')
) ap
    ON base.客户名称 = ap.FCUSTOMER
LEFT JOIN 客户月管理费用 cm
    ON base.客户名称 = cm.FCUSTOMERNAME
LEFT JOIN (
    SELECT
        RTRIM(LTRIM(s.FRetcustNAME)) AS FRetcustNAME,
        ROUND(
            SUM(
                COALESCE(TRY_CONVERT(DECIMAL(18, 4), s.FRealQty), 0) *
                COALESCE(TRY_CONVERT(DECIMAL(18, 4), m.F_ORA_TEXT_9SB), 0)
            ),
            2
        ) AS 退货费用
    FROM sal_returnstock s
    LEFT JOIN bd_material m
        ON s.FMaterialFNUMBER = m.FNUMBER
    WHERE s.FRetcustNAME IS NOT NULL
      AND RTRIM(LTRIM(s.FRetcustNAME)) <> ''
      ${if(len(START) == 0, "", "AND TRY_CONVERT(DATE, s.FDate) >= CONVERT(DATE, '" + START + "-01', 23)")}
      ${if(len(END) == 0, "", "AND TRY_CONVERT(DATE, s.FDate) < DATEADD(MONTH, 1, CONVERT(DATE, '" + END + "-01', 23))")}
      ${if(len(客户) == 0, "", "AND RTRIM(LTRIM(s.FRetcustNAME)) = N'" + 客户 + "'")}
    GROUP BY RTRIM(LTRIM(s.FRetcustNAME))
) ret
    ON base.客户名称 = ret.FRetcustNAME
OUTER APPLY (
    SELECT SUM(s2.借方金额) AS 借方金额
    FROM 客户罚款明细 s2
    WHERE base.客户名称 LIKE s2.客户名称 + '%'
       OR s2.客户名称 LIKE base.客户名称 + '%'
) s2
LEFT JOIN 客户成本汇总 cb
    ON base.客户名称 = cb.客户名称
ORDER BY base.客户名称;
