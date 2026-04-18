using System.Security.Cryptography;
using System.Text;

namespace Kingdee.SyncTool.Infrastructure.Security;

internal static class Fernet
{
    public static bool TryDecrypt(string token, byte[] key, out string plaintext)
    {
        plaintext = string.Empty;
        if (string.IsNullOrWhiteSpace(token) || key.Length != 32)
        {
            return false;
        }

        byte[] data;
        try
        {
            data = Base64Url.Decode(token);
        }
        catch
        {
            return false;
        }

        // version(1) + timestamp(8) + iv(16) + hmac(32)
        if (data.Length < 1 + 8 + 16 + 32)
        {
            return false;
        }

        if (data[0] != 0x80)
        {
            return false;
        }

        var signingKey = key.AsSpan(0, 16).ToArray();
        var encryptionKey = key.AsSpan(16, 16).ToArray();

        var signed = data.AsSpan(0, data.Length - 32).ToArray();
        var signature = data.AsSpan(data.Length - 32, 32).ToArray();

        byte[] computed;
        using (var hmac = new HMACSHA256(signingKey))
        {
            computed = hmac.ComputeHash(signed);
        }

        if (!CryptographicOperations.FixedTimeEquals(signature, computed))
        {
            return false;
        }

        var iv = data.AsSpan(9, 16).ToArray();
        var cipherText = data.AsSpan(25, data.Length - 25 - 32).ToArray();

        try
        {
            using var aes = Aes.Create();
            aes.Mode = CipherMode.CBC;
            aes.Padding = PaddingMode.PKCS7;
            aes.Key = encryptionKey;
            aes.IV = iv;

            using var decryptor = aes.CreateDecryptor();
            var plainBytes = decryptor.TransformFinalBlock(cipherText, 0, cipherText.Length);
            plaintext = Encoding.UTF8.GetString(plainBytes);
            return true;
        }
        catch
        {
            return false;
        }
    }
}
