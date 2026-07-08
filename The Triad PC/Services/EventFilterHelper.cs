using System.Text.Json;
using Microsoft.AspNetCore.Mvc;

namespace TheTriadPCNightCrew.Services;

public enum WhenFilter
{
    Today,
    Weekend,
    ThisWeek,
    All
}

public static class EventFilterHelper
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public static (DateTimeOffset? StartUtc, DateTimeOffset? EndUtc) BuildDateRangeUtc(WhenFilter when)
    {
        var today = DateTime.Today;
        var offset = TimeZoneInfo.Local.GetUtcOffset(today);

        DateTime startLocal;
        DateTime endLocal;

        switch (when)
        {
            case WhenFilter.Today:
                startLocal = today;
                endLocal = today.AddDays(1).AddTicks(-1);
                break;

            case WhenFilter.ThisWeek:
                startLocal = today;
                endLocal = today.AddDays(7).AddTicks(-1);
                break;

            case WhenFilter.Weekend:
                if (today.DayOfWeek == DayOfWeek.Sunday)
                {
                    startLocal = today.AddDays(-1);
                }
                else
                {
                    var daysUntilSat = ((int)DayOfWeek.Saturday - (int)today.DayOfWeek + 7) % 7;
                    startLocal = today.AddDays(daysUntilSat);
                }
                endLocal = startLocal.AddDays(2).AddTicks(-1);
                break;

            default:
                return (null, null);
        }

        var start = new DateTimeOffset(startLocal, offset).ToUniversalTime();
        var end = new DateTimeOffset(endLocal, offset).ToUniversalTime();
        return (start, end);
    }

    public static string FormatDateTime(string? localDate, string? localTime)
    {
        if (string.IsNullOrWhiteSpace(localDate))
        {
            return "Data da confermare";
        }

        return string.IsNullOrWhiteSpace(localTime) ? localDate : $"{localDate} · {localTime}";
    }

    public static string FormatVenueLine(string? venue, string? address, string? city)
    {
        var v = (venue ?? "").Trim();
        var a = (address ?? "").Trim();
        var c = (city ?? "").Trim();

        if (v.Length == 0 && a.Length == 0 && c.Length == 0) return "Da confermare";
        if (a.Length == 0 && c.Length == 0) return v;
        if (a.Length == 0) return v.Length == 0 ? c : $"{v} · {c}";
        if (c.Length == 0) return v.Length == 0 ? a : $"{v} · {a}";
        if (v.Length == 0) return $"{a} · {c}";
        return $"{v} · {a} · {c}";
    }

    public static ProblemDetails? TryParseProblemDetails(string? json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return null;
        }

        try
        {
            return JsonSerializer.Deserialize<ProblemDetails>(json, JsonOptions);
        }
        catch
        {
            return null;
        }
    }

    public static string BuildUserFriendlyError(ProblemDetails? problem, System.Net.HttpStatusCode statusCode)
    {
        if (!string.IsNullOrWhiteSpace(problem?.Detail))
        {
            return problem!.Detail!;
        }

        if (!string.IsNullOrWhiteSpace(problem?.Title))
        {
            return problem!.Title!;
        }

        var status = problem?.Status ?? (int)statusCode;
        return $"Errore nel caricamento del feed ({status}). Riprova tra poco.";
    }
}
