
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'sync_runs' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.sync_runs (
        id               BIGINT IDENTITY(1,1) PRIMARY KEY,
        run_id           NVARCHAR(64)  NOT NULL,
        sync_type        NVARCHAR(32)  NOT NULL,
        status           NVARCHAR(32)  NOT NULL,
        forms_synced     NVARCHAR(MAX),
        total_records    BIGINT        NOT NULL DEFAULT 0,
        start_time       DATETIME2     NOT NULL,
        end_time         DATETIME2,
        duration_seconds FLOAT,
        message          NVARCHAR(512),
        created_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_sync_runs_run_id UNIQUE (run_id)
    );

    CREATE INDEX IX_sync_runs_start_time ON dbo.sync_runs (start_time DESC);
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'sync_form_stats' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.sync_form_stats (
        id               BIGINT IDENTITY(1,1) PRIMARY KEY,
        run_id           NVARCHAR(64)  NOT NULL,
        form_name        NVARCHAR(128) NOT NULL,
        table_name       NVARCHAR(128) NOT NULL,
        fetched_count    BIGINT        NOT NULL DEFAULT 0,
        inserted_count   BIGINT        NOT NULL DEFAULT 0,
        error_count      INT           NOT NULL DEFAULT 0,
        status           NVARCHAR(32)  NOT NULL,
        duration_seconds FLOAT,
        created_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_sync_form_stats_run
            FOREIGN KEY (run_id) REFERENCES dbo.sync_runs (run_id)
            ON DELETE CASCADE
    );

    CREATE INDEX IX_sync_form_stats_run_id ON dbo.sync_form_stats (run_id);
    CREATE INDEX IX_sync_form_stats_form_name_time ON dbo.sync_form_stats (form_name, created_at DESC);
    CREATE INDEX IX_sync_form_stats_table_name_time ON dbo.sync_form_stats (table_name, created_at DESC);
END

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'sync_errors' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.sync_errors (
        id            BIGINT IDENTITY(1,1) PRIMARY KEY,
        run_id        NVARCHAR(64)  NOT NULL,
        form_name     NVARCHAR(128) NOT NULL,
        error_type    NVARCHAR(128),
        error_message NVARCHAR(MAX) NOT NULL,
        created_at    DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_sync_errors_run
            FOREIGN KEY (run_id) REFERENCES dbo.sync_runs (run_id)
            ON DELETE CASCADE
    );

    CREATE INDEX IX_sync_errors_run_id ON dbo.sync_errors (run_id);
    CREATE INDEX IX_sync_errors_form_name_time ON dbo.sync_errors (form_name, created_at DESC);
END
