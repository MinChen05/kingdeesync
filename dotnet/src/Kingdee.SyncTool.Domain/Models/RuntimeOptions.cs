using Kingdee.SyncTool.Domain.Enums;

namespace Kingdee.SyncTool.Domain.Models;

public sealed class KingdeeApiOptions
{
    public string LoginUrl { get; init; } = string.Empty;

    public string QueryUrl { get; init; } = string.Empty;

    public string AccountId { get; init; } = string.Empty;

    public string Username { get; init; } = string.Empty;

    public string Password { get; init; } = string.Empty;

    public string Lcid { get; init; } = "2052";

    public bool KeepSessionAlive { get; init; } = true;

    public int KeepAliveIntervalSeconds { get; init; } = 600;

    public bool AutoLogoutOnExit { get; init; } = false;

    public double RateLimitQps { get; init; } = 2.0;

    public int RequestTimeoutSeconds { get; init; } = 0;

    public int PageSize { get; init; } = 20000;

    public int MaxPages { get; init; } = 100000;
}

public sealed class SqlServerConnectionOptions
{
    public string Host { get; init; } = "127.0.0.1";

    public int Port { get; init; } = 1433;

    public string Database { get; init; } = string.Empty;

    public string User { get; init; } = string.Empty;

    public string Password { get; init; } = string.Empty;

    public string Driver { get; init; } = "ODBC Driver 17 for SQL Server";

    public bool TrustedConnection { get; init; } = false;
}

public sealed class MySqlConnectionOptions
{
    public string Host { get; init; } = "127.0.0.1";

    public int Port { get; init; } = 3306;

    public string Database { get; init; } = string.Empty;

    public string User { get; init; } = string.Empty;

    public string Password { get; init; } = string.Empty;
}

public sealed class DatabaseOptions
{
    public string Type { get; init; } = "sqlserver";

    public SqlServerConnectionOptions SqlServer { get; init; } = new();

    public MySqlConnectionOptions MySql { get; init; } = new();
}

public sealed class SyncRuntimeOptions
{
    public bool AutoSync { get; init; }

    public int IntervalMinutes { get; init; } = 60;

    public SyncType SyncType { get; init; } = SyncType.Incremental;

    public IReadOnlyList<string> DefaultForms { get; init; } = Array.Empty<string>();

    public int TableConcurrency { get; init; } = 1;

    public int FetchConcurrency { get; init; } = 1;

    public int TimeWindowDays { get; init; } = 30;

    public string FullStartDate { get; init; } = "2000-01-01";
}
