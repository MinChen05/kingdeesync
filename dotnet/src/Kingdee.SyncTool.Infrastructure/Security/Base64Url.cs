using System.Text;

namespace Kingdee.SyncTool.Infrastructure.Security;

internal static class Base64Url
{
    public static byte[] Decode(string value)
    {
        var normalized = value.Replace('-', '+').Replace('_', '/');
        var padding = normalized.Length % 4;
        if (padding > 0)
        {
            normalized = normalized.PadRight(normalized.Length + (4 - padding), '=');
        }

        return Convert.FromBase64String(normalized);
    }

    public static string Encode(ReadOnlySpan<byte> value)
    {
        var base64 = Convert.ToBase64String(value);
        return base64.Replace('+', '-').Replace('/', '_').TrimEnd('=');
    }

    public static bool TryDecodeToUtf8(string value, out string text)
    {
        try
        {
            var bytes = Decode(value);
            text = Encoding.UTF8.GetString(bytes);
            return true;
        }
        catch
        {
            text = string.Empty;
            return false;
        }
    }
}
