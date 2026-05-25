using System.Text.Json;
using Microsoft.JSInterop;

namespace TheTriadPCNightCrew.Services;

public sealed class FavoritesStore
{
    private const string StorageKey = "nc:favorites:v1";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly IJSRuntime _js;

    public FavoritesStore(IJSRuntime js)
    {
        _js = js;
    }

    public async Task<IReadOnlyList<FavoriteEvent>> GetAllAsync(CancellationToken ct = default)
    {
        var list = await ReadAsync(ct);
        return list
            .OrderByDescending(x => x.AddedAtUtc)
            .ToList();
    }

    public async Task<bool> ContainsAsync(string id, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(id)) return false;
        var list = await ReadAsync(ct);
        return list.Any(x => string.Equals(x.Id, id, StringComparison.OrdinalIgnoreCase));
    }

    public async Task AddOrUpdateAsync(FavoriteEvent evt, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(evt.Id)) return;

        var list = await ReadAsync(ct);
        var idx = list.FindIndex(x => string.Equals(x.Id, evt.Id, StringComparison.OrdinalIgnoreCase));
        if (idx >= 0)
        {
            var existing = list[idx];
            list[idx] = evt with { AddedAtUtc = existing.AddedAtUtc };
        }
        else
        {
            list.Add(evt with { AddedAtUtc = evt.AddedAtUtc == default ? DateTimeOffset.UtcNow : evt.AddedAtUtc });
        }

        if (list.Count > 200)
        {
            list = list
                .OrderByDescending(x => x.AddedAtUtc)
                .Take(200)
                .ToList();
        }

        await WriteAsync(list, ct);
    }

    public async Task RemoveAsync(string id, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(id)) return;
        var list = await ReadAsync(ct);
        list.RemoveAll(x => string.Equals(x.Id, id, StringComparison.OrdinalIgnoreCase));
        await WriteAsync(list, ct);
    }

    public async Task<bool> ToggleAsync(FavoriteEvent evt, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(evt.Id)) return false;
        var list = await ReadAsync(ct);
        var idx = list.FindIndex(x => string.Equals(x.Id, evt.Id, StringComparison.OrdinalIgnoreCase));
        if (idx >= 0)
        {
            list.RemoveAt(idx);
            await WriteAsync(list, ct);
            return false;
        }

        list.Add(evt with { AddedAtUtc = DateTimeOffset.UtcNow });
        await WriteAsync(list, ct);
        return true;
    }

    private async Task<List<FavoriteEvent>> ReadAsync(CancellationToken ct)
    {
        try
        {
            var json = await _js.InvokeAsync<string?>("ncStorage.getItem", ct, StorageKey);
            if (string.IsNullOrWhiteSpace(json))
            {
                return [];
            }

            var parsed = JsonSerializer.Deserialize<List<FavoriteEvent>>(json, JsonOptions);
            return parsed ?? [];
        }
        catch
        {
            return [];
        }
    }

    private async Task WriteAsync(List<FavoriteEvent> list, CancellationToken ct)
    {
        try
        {
            var json = JsonSerializer.Serialize(list, JsonOptions);
            await _js.InvokeVoidAsync("ncStorage.setItem", ct, StorageKey, json);
        }
        catch
        {
        }
    }
}

public sealed record FavoriteEvent(
    string Id,
    string Slug,
    string Name,
    string? City,
    string? Venue,
    string? Address,
    string? LocalDate,
    string? LocalTime,
    string? ImageUrl,
    string? TicketmasterUrl,
    DateTimeOffset AddedAtUtc
);
