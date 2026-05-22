using System.Globalization;
using System.Text;

namespace TheTriadPCNightCrew.Services;

public static class TicketmasterSlug
{
    private const string Separator = "--";

    public static string Build(string name, string id)
    {
        var safeName = Slugify(name);
        var safeId = (id ?? "").Trim();
        if (string.IsNullOrWhiteSpace(safeId))
        {
            return safeName;
        }

        return $"{safeName}{Separator}{safeId}";
    }

    public static bool TryExtractId(string slug, out string id)
    {
        id = "";
        if (string.IsNullOrWhiteSpace(slug))
        {
            return false;
        }

        var idx = slug.LastIndexOf(Separator, StringComparison.Ordinal);
        if (idx >= 0 && idx + Separator.Length < slug.Length)
        {
            var candidate = slug[(idx + Separator.Length)..].Trim();
            if (!string.IsNullOrWhiteSpace(candidate))
            {
                id = candidate;
                return true;
            }
        }

        if (slug.StartsWith("tm-", StringComparison.OrdinalIgnoreCase) && slug.Length > 3)
        {
            id = slug[3..].Trim();
            return !string.IsNullOrWhiteSpace(id);
        }

        var lastDash = slug.LastIndexOf('-');
        if (lastDash >= 0 && lastDash + 1 < slug.Length)
        {
            var candidate = slug[(lastDash + 1)..].Trim();
            if (candidate.Length >= 8 && candidate.All(char.IsLetterOrDigit))
            {
                id = candidate;
                return true;
            }
        }

        return false;
    }

    public static string Slugify(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return "event";
        }

        var normalized = text.Trim().ToLowerInvariant().Normalize(NormalizationForm.FormD);
        var sb = new StringBuilder(normalized.Length);
        var lastWasDash = false;

        foreach (var c in normalized)
        {
            var category = CharUnicodeInfo.GetUnicodeCategory(c);
            if (category == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsLetterOrDigit(c))
            {
                sb.Append(c);
                lastWasDash = false;
                continue;
            }

            if (c is ' ' or '-' or '_' or '.' or '/' or '\\' or ':' or ';' or ',' or '|' or '+')
            {
                if (!lastWasDash && sb.Length > 0)
                {
                    sb.Append('-');
                    lastWasDash = true;
                }
            }
        }

        var result = sb
            .ToString()
            .Trim('-')
            .Replace("--", "-", StringComparison.Ordinal);

        return string.IsNullOrWhiteSpace(result) ? "event" : result;
    }
}
