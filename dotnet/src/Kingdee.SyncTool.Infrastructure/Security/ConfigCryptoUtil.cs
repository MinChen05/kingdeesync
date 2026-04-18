using System.Net.NetworkInformation;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32;

namespace Kingdee.SyncTool.Infrastructure.Security;

public static class ConfigCryptoUtil
{
    private static readonly byte[] DefaultSalt = Encoding.UTF8.GetBytes("kingdee_sync_salt_value");
    private static readonly object SaltLock = new();
    private static byte[]? CachedInstallSalt;
    private static string? CachedMachineId;

    public static string DecryptIfNeeded(string rawValue, string configPath)
    {
        if (string.IsNullOrWhiteSpace(rawValue))
        {
            return rawValue;
        }

        const string prefix = "encrypted:";
        if (!rawValue.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            return rawValue;
        }

        var encryptedBody = rawValue[prefix.Length..].Trim();
        var plain = Decrypt(encryptedBody, configPath);
        return string.IsNullOrWhiteSpace(plain) ? rawValue : plain;
    }

    public static string Decrypt(string encrypted, string configPath)
    {
        if (string.IsNullOrWhiteSpace(encrypted))
        {
            return string.Empty;
        }

        var machineId = GetMachineId();

        var primarySalt = GetOrCreateInstallSalt(configPath);
        var primaryKey = GenerateKey(machineId, primarySalt);
        if (TryDecryptWithKey(encrypted, primaryKey, out var plaintext))
        {
            return plaintext;
        }

        var fallbackKey = GenerateKey(machineId, DefaultSalt);
        if (TryDecryptWithKey(encrypted, fallbackKey, out plaintext))
        {
            return plaintext;
        }

        var wmicMachineId = TryGetWmicMachineId();
        if (!string.IsNullOrWhiteSpace(wmicMachineId))
        {
            var wmicKey = GenerateKey(wmicMachineId, DefaultSalt);
            if (TryDecryptWithKey(encrypted, wmicKey, out plaintext))
            {
                return plaintext;
            }
        }

        return string.Empty;
    }

    private static bool TryDecryptWithKey(string encrypted, byte[] rawKey, out string plaintext)
    {
        // Python stores: base64url(fernet-token-bytes).
        if (Base64Url.TryDecodeToUtf8(encrypted, out var token) &&
            Fernet.TryDecrypt(token, rawKey, out plaintext))
        {
            return true;
        }

        // Fallback: encrypted value itself is the fernet token.
        if (Fernet.TryDecrypt(encrypted, rawKey, out plaintext))
        {
            return true;
        }

        plaintext = string.Empty;
        return false;
    }

    private static byte[] GenerateKey(string password, byte[] salt)
    {
        var passwordBytes = Encoding.UTF8.GetBytes(password);
        using var kdf = new Rfc2898DeriveBytes(passwordBytes, salt, 100_000, HashAlgorithmName.SHA256);
        return kdf.GetBytes(32);
    }

    private static byte[] GetOrCreateInstallSalt(string configPath)
    {
        if (CachedInstallSalt is not null)
        {
            return CachedInstallSalt;
        }

        lock (SaltLock)
        {
            if (CachedInstallSalt is not null)
            {
                return CachedInstallSalt;
            }

            var configDir = Path.GetDirectoryName(Path.GetFullPath(configPath)) ?? Directory.GetCurrentDirectory();
            var saltPath = Path.Combine(configDir, ".install_salt");

            if (File.Exists(saltPath))
            {
                var existing = File.ReadAllBytes(saltPath);
                if (existing.Length >= 16)
                {
                    CachedInstallSalt = existing;
                    return existing;
                }
            }

            var generated = RandomNumberGenerator.GetBytes(32);
            try
            {
                File.WriteAllBytes(saltPath, generated);
            }
            catch
            {
                // Ignore write failure, keep runtime salt.
            }

            CachedInstallSalt = generated;
            return generated;
        }
    }

    private static string GetMachineId()
    {
        if (!string.IsNullOrWhiteSpace(CachedMachineId))
        {
            return CachedMachineId;
        }

        if (OperatingSystem.IsWindows())
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Cryptography");
                var guid = key?.GetValue("MachineGuid")?.ToString();
                if (!string.IsNullOrWhiteSpace(guid))
                {
                    CachedMachineId = guid.Trim();
                    return CachedMachineId;
                }
            }
            catch
            {
                // Ignore registry read failure.
            }

            var wmic = TryGetWmicMachineId();
            if (!string.IsNullOrWhiteSpace(wmic))
            {
                CachedMachineId = wmic;
                return CachedMachineId;
            }
        }

        try
        {
            var nic = NetworkInterface.GetAllNetworkInterfaces()
                .FirstOrDefault(n => n.OperationalStatus == OperationalStatus.Up);
            if (nic is not null)
            {
                var mac = nic.GetPhysicalAddress().ToString();
                if (!string.IsNullOrWhiteSpace(mac))
                {
                    CachedMachineId = mac;
                    return CachedMachineId;
                }
            }
        }
        catch
        {
            // Ignore network interface failure.
        }

        CachedMachineId = "kingdee_sync_default_machine_id";
        return CachedMachineId;
    }

    private static string? TryGetWmicMachineId()
    {
        try
        {
            if (!OperatingSystem.IsWindows())
            {
                return null;
            }

            var psi = new System.Diagnostics.ProcessStartInfo
            {
                FileName = "wmic",
                Arguments = "csproduct get uuid",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };

            using var process = System.Diagnostics.Process.Start(psi);
            if (process is null)
            {
                return null;
            }

            var output = process.StandardOutput.ReadToEnd();
            process.WaitForExit(3000);
            var lines = output
                .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Where(static line => !line.Equals("UUID", StringComparison.OrdinalIgnoreCase))
                .ToArray();

            return lines.FirstOrDefault();
        }
        catch
        {
            return null;
        }
    }
}
