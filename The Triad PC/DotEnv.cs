namespace TheTriadPCNightCrew;

internal static class DotEnv
{
    internal static int LoadFromCwdIfPresent(string fileName = ".env")
    {
        var fromCwdTree = FindUpwards(Directory.GetCurrentDirectory(), fileName, maxDepth: 6);
        if (!string.IsNullOrWhiteSpace(fromCwdTree))
        {
            return LoadFile(fromCwdTree);
        }

        var baseDirPath = Path.Combine(AppContext.BaseDirectory, fileName);
        if (File.Exists(baseDirPath))
        {
            return LoadFile(baseDirPath);
        }

        var fromBaseTree = FindUpwards(AppContext.BaseDirectory, fileName, maxDepth: 6);
        if (!string.IsNullOrWhiteSpace(fromBaseTree))
        {
            return LoadFile(fromBaseTree);
        }

        return 0;
    }

    private static string? FindUpwards(string startDirectory, string fileName, int maxDepth)
    {
        try
        {
            var current = new DirectoryInfo(startDirectory);
            for (var i = 0; i < Math.Max(1, maxDepth); i++)
            {
                var candidate = Path.Combine(current.FullName, fileName);
                if (File.Exists(candidate))
                {
                    return candidate;
                }

                if (current.Parent is null)
                {
                    break;
                }

                current = current.Parent;
            }
        }
        catch
        {
        }

        return null;
    }

    private static int LoadFile(string path)
    {
        var count = 0;

        foreach (var raw in File.ReadLines(path))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#'))
            {
                continue;
            }

            if (line.StartsWith("export ", StringComparison.Ordinal))
            {
                line = line["export ".Length..].TrimStart();
            }

            var eq = line.IndexOf('=');
            if (eq <= 0)
            {
                continue;
            }

            var key = line[..eq].Trim();
            if (string.IsNullOrWhiteSpace(key))
            {
                continue;
            }

            var existing = Environment.GetEnvironmentVariable(key);
            if (!string.IsNullOrEmpty(existing))
            {
                continue;
            }

            var valuePart = line[(eq + 1)..].Trim();
            var value = ParseValue(valuePart);

            Environment.SetEnvironmentVariable(key, value);
            count++;
        }

        return count;
    }

    private static string ParseValue(string valuePart)
    {
        if (valuePart.Length == 0)
        {
            return string.Empty;
        }

        if ((valuePart[0] == '"' && valuePart.EndsWith('"')) ||
            (valuePart[0] == '\'' && valuePart.EndsWith('\'')))
        {
            var quote = valuePart[0];
            var inner = valuePart[1..^1];
            return quote == '"' ? UnescapeDoubleQuoted(inner) : inner;
        }

        var cut = IndexOfInlineCommentStart(valuePart);
        if (cut >= 0)
        {
            valuePart = valuePart[..cut].TrimEnd();
        }

        return valuePart;
    }

    private static int IndexOfInlineCommentStart(string valuePart)
    {
        for (var i = 0; i < valuePart.Length; i++)
        {
            if (valuePart[i] != '#')
            {
                continue;
            }

            if (i == 0 || char.IsWhiteSpace(valuePart[i - 1]))
            {
                return i;
            }
        }

        return -1;
    }

    private static string UnescapeDoubleQuoted(string s)
    {
        return s
            .Replace("\\n", "\n", StringComparison.Ordinal)
            .Replace("\\r", "\r", StringComparison.Ordinal)
            .Replace("\\t", "\t", StringComparison.Ordinal)
            .Replace("\\\"", "\"", StringComparison.Ordinal)
            .Replace("\\\\", "\\", StringComparison.Ordinal);
    }
}
