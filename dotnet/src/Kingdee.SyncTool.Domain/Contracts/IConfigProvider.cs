using Kingdee.SyncTool.Domain.Models;

namespace Kingdee.SyncTool.Domain.Contracts;

public interface IConfigProvider
{
    string ConfigPath { get; }

    KingdeeApiOptions GetKingdeeOptions();

    DatabaseOptions GetDatabaseOptions();

    SyncRuntimeOptions GetSyncOptions();

    IReadOnlyDictionary<string, string> GetTableMappings();

    IReadOnlyDictionary<string, string> GetInsertMethodMappings();

    IReadOnlyDictionary<string, FormQueryOptions> GetFormQueries();

    string GetIncrementalField(string key);
}
