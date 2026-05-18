SET NOCOUNT ON;

DECLARE @ChildCode NVARCHAR(50) = N'100301010126';
DECLARE @StartDate DATE = '2025-04-01';
DECLARE @EndDate DATE = '2026-04-01';

/*
用途：
1. 对照现有 sp_BOM_TopLevel_Query 的统计口径
2. 验证“排除替代组(FREPLACEGROUP<>0)”后结果是否贴近客户端

说明：
- current_*：保留现有逻辑
- exclude_replacegroup_*：在起始命中、向上递归、顶层判定三处都要求 FREPLACEGROUP=0
- direct_map_*：直接命中 @ChildCode 的 BOM 行分布，用来判断是否全部落在替代组
*/

DROP TABLE IF EXISTS #DirectMap;
DROP TABLE IF EXISTS #SeedCurrent;
DROP TABLE IF EXISTS #TopCurrent;
DROP TABLE IF EXISTS #SeedNoReplace;
DROP TABLE IF EXISTS #TopNoReplace;

SELECT
    pm.FNUMBER AS top_number,
    pm.FNAME AS top_name,
    bc.FENTRYID,
    bc.FSEQ,
    bc.FCHILDNUMBER,
    bc.FCHILDNAME,
    bc.FREPLACEGROUP,
    bc.FISSUETYPE,
    bc.FBACKFLUSHTYPE,
    bc.FQTY,
    bc.FNUMERATOR,
    bc.FDENOMINATOR,
    bc.FMODIFYDATE
INTO #DirectMap
FROM eng_bomchild bc
INNER JOIN bd_material pm ON pm.FMATERIALID = bc.FMATERIALID
WHERE bc.FCHILDNUMBER = @ChildCode;

CREATE INDEX IX_DirectMap_TopNumber ON #DirectMap(top_number);

SELECT DISTINCT
    bc.FMATERIALID AS TopID,
    bc.FMATERIALID AS CheckID,
    bc.FCHILDNUMBER AS OrigChild
INTO #SeedCurrent
FROM eng_bomchild bc
WHERE bc.FCHILDNUMBER = @ChildCode;

CREATE INDEX IX_SeedCurrent_CheckID ON #SeedCurrent(CheckID);

DECLARE @CurrentRows INT = 1;

WHILE @CurrentRows > 0
BEGIN
    INSERT INTO #SeedCurrent (TopID, CheckID, OrigChild)
    SELECT DISTINCT
        bc_up.FMATERIALID,
        bc_up.FMATERIALID,
        seed.OrigChild
    FROM #SeedCurrent seed
    INNER JOIN bd_material m ON seed.CheckID = m.FMATERIALID
    INNER JOIN eng_bomchild bc_up ON bc_up.FCHILDNUMBER = m.FNUMBER
    WHERE NOT EXISTS (
        SELECT 1
        FROM #SeedCurrent existed
        WHERE existed.TopID = bc_up.FMATERIALID
          AND existed.CheckID = bc_up.FMATERIALID
          AND existed.OrigChild = seed.OrigChild
    );

    SET @CurrentRows = @@ROWCOUNT;
END;

SELECT DISTINCT
    seed.TopID
INTO #TopCurrent
FROM #SeedCurrent seed
WHERE NOT EXISTS (
    SELECT 1
    FROM bd_material m
    INNER JOIN eng_bomchild bc ON bc.FCHILDNUMBER = m.FNUMBER
    WHERE m.FMATERIALID = seed.CheckID
);

CREATE INDEX IX_TopCurrent_TopID ON #TopCurrent(TopID);

SELECT DISTINCT
    bc.FMATERIALID AS TopID,
    bc.FMATERIALID AS CheckID,
    bc.FCHILDNUMBER AS OrigChild
INTO #SeedNoReplace
FROM eng_bomchild bc
WHERE bc.FCHILDNUMBER = @ChildCode
  AND ISNULL(bc.FREPLACEGROUP, 0) = 0;

CREATE INDEX IX_SeedNoReplace_CheckID ON #SeedNoReplace(CheckID);

DECLARE @NoReplaceRows INT = 1;

WHILE @NoReplaceRows > 0
BEGIN
    INSERT INTO #SeedNoReplace (TopID, CheckID, OrigChild)
    SELECT DISTINCT
        bc_up.FMATERIALID,
        bc_up.FMATERIALID,
        seed.OrigChild
    FROM #SeedNoReplace seed
    INNER JOIN bd_material m ON seed.CheckID = m.FMATERIALID
    INNER JOIN eng_bomchild bc_up ON bc_up.FCHILDNUMBER = m.FNUMBER
    WHERE ISNULL(bc_up.FREPLACEGROUP, 0) = 0
      AND NOT EXISTS (
          SELECT 1
          FROM #SeedNoReplace existed
          WHERE existed.TopID = bc_up.FMATERIALID
            AND existed.CheckID = bc_up.FMATERIALID
            AND existed.OrigChild = seed.OrigChild
      );

    SET @NoReplaceRows = @@ROWCOUNT;
END;

SELECT DISTINCT
    seed.TopID
INTO #TopNoReplace
FROM #SeedNoReplace seed
WHERE NOT EXISTS (
    SELECT 1
    FROM bd_material m
    INNER JOIN eng_bomchild bc ON bc.FCHILDNUMBER = m.FNUMBER
    WHERE m.FMATERIALID = seed.CheckID
      AND ISNULL(bc.FREPLACEGROUP, 0) = 0
);

CREATE INDEX IX_TopNoReplace_TopID ON #TopNoReplace(TopID);

SELECT
    'direct_map_rows' AS metric,
    CAST(COUNT(*) AS BIGINT) AS value
FROM #DirectMap
UNION ALL
SELECT
    'direct_map_replacegroup_nonzero',
    CAST(SUM(CASE WHEN ISNULL(FREPLACEGROUP, 0) <> 0 THEN 1 ELSE 0 END) AS BIGINT)
FROM #DirectMap
UNION ALL
SELECT
    'current_top_count',
    CAST(COUNT(*) AS BIGINT)
FROM #TopCurrent
UNION ALL
SELECT
    'current_qty_ge100',
    CAST(ISNULL(SUM(os.FREALQTY), 0) AS BIGINT)
FROM #TopCurrent topx
INNER JOIN bd_material m ON topx.TopID = m.FMATERIALID
INNER JOIN sal_outstock os ON os.FMATERIALNUMBER = m.FNUMBER
WHERE os.FREALQTY >= 100
  AND os.FDATE >= @StartDate
  AND os.FDATE <= @EndDate
UNION ALL
SELECT
    'exclude_replacegroup_top_count',
    CAST(COUNT(*) AS BIGINT)
FROM #TopNoReplace
UNION ALL
SELECT
    'exclude_replacegroup_qty_ge100',
    CAST(ISNULL(SUM(os.FREALQTY), 0) AS BIGINT)
FROM #TopNoReplace topx
INNER JOIN bd_material m ON topx.TopID = m.FMATERIALID
INNER JOIN sal_outstock os ON os.FMATERIALNUMBER = m.FNUMBER
WHERE os.FREALQTY >= 100
  AND os.FDATE >= @StartDate
  AND os.FDATE <= @EndDate;

SELECT TOP (50)
    top_number,
    top_name,
    FENTRYID,
    FSEQ,
    FREPLACEGROUP,
    FQTY,
    FNUMERATOR,
    FDENOMINATOR,
    FMODIFYDATE
FROM #DirectMap
ORDER BY top_number, FSEQ;

SELECT TOP (50)
    m.FNUMBER AS top_material_number,
    SUM(os.FREALQTY) AS qty_ge100
FROM #TopCurrent topx
INNER JOIN bd_material m ON topx.TopID = m.FMATERIALID
INNER JOIN sal_outstock os ON os.FMATERIALNUMBER = m.FNUMBER
WHERE os.FREALQTY >= 100
  AND os.FDATE >= @StartDate
  AND os.FDATE <= @EndDate
GROUP BY m.FNUMBER
ORDER BY qty_ge100 DESC, top_material_number;
