using System.Net.Http.Json;
using System.Net;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace TheTriadPCNightCrew.Services;

public sealed class TicketmasterApi
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IConfiguration _configuration;
    private readonly ILogger<TicketmasterApi> _logger;
    private readonly JsonSerializerOptions _jsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true
    };

    public TicketmasterApi(
        IHttpClientFactory httpClientFactory,
        IConfiguration configuration,
        ILogger<TicketmasterApi> logger)
    {
        _httpClientFactory = httpClientFactory;
        _configuration = configuration;
        _logger = logger;
    }

    public async Task<PagedResult<TicketmasterEventListItem>> SearchEventsAsync(TicketmasterEventsQuery query, CancellationToken ct)
    {
        var apiKey = GetTicketmasterApiKeyOrThrow();

        var size = Clamp(query.Size, min: 1, max: 200);
        var page = Math.Max(0, query.Page);

        var qs = BuildQueryString(
            ("apikey", apiKey),
            ("keyword", query.Keyword),
            ("city", query.City),
            ("classificationName", query.ClassificationName),
            ("startDateTime", query.StartDateTime?.ToString("O")),
            ("endDateTime", query.EndDateTime?.ToString("O")),
            ("latlong", query.LatLong),
            ("radius", query.Radius?.ToString()),
            ("unit", query.Unit),
            ("sort", query.Sort),
            ("countryCode", query.CountryCode),
            ("locale", query.Locale),
            ("size", size.ToString()),
            ("page", page.ToString())
        );

        var http = _httpClientFactory.CreateClient("Ticketmaster");
        var endpoint = "events.json";
        var url = $"{endpoint}{qs}";

        TicketmasterSearchRaw? raw;
        raw = await GetFromJsonSafeAsync<TicketmasterSearchRaw>(http, url, endpoint, returnNullOnNotFound: false, ct);

        var items = (raw?._embedded?.events ?? [])
            .Select(MapListItem)
            .Where(x => x is not null)
            .Select(x => x!)
            .ToList();

        var pageInfo = raw?.page ?? new TicketmasterPageRaw();
        return new PagedResult<TicketmasterEventListItem>(
            Items: items,
            Page: pageInfo.number,
            Size: pageInfo.size,
            TotalPages: pageInfo.totalPages,
            TotalItems: pageInfo.totalElements
        );
    }

    public async Task<TicketmasterEventDetail?> GetEventAsync(string id, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return null;
        }

        var apiKey = GetTicketmasterApiKeyOrThrow();

        var qs = BuildQueryString(
            ("apikey", apiKey),
            ("locale", _configuration["Ticketmaster:Locale"] ?? "it"),
            ("countryCode", _configuration["Ticketmaster:CountryCode"] ?? "IT")
        );

        var http = _httpClientFactory.CreateClient("Ticketmaster");
        var endpoint = "events/{id}.json";
        var url = $"events/{Uri.EscapeDataString(id)}.json{qs}";

        var raw = await GetFromJsonSafeAsync<TicketmasterEventRaw>(http, url, endpoint, returnNullOnNotFound: true, ct);

        if (raw is null)
        {
            return null;
        }

        return MapDetail(raw);
    }

    private string GetTicketmasterApiKeyOrThrow()
    {
        var apiKey = _configuration["TICKETMASTER_API_KEY"] ?? _configuration["Ticketmaster:ApiKey"];
        if (string.IsNullOrWhiteSpace(apiKey))
        {
            throw new InvalidOperationException(
                "Ticketmaster ApiKey mancante. Imposta env var TICKETMASTER_API_KEY oppure Ticketmaster:ApiKey in appsettings.");
        }

        return apiKey;
    }

    private async Task<T?> GetFromJsonSafeAsync<T>(
        HttpClient http,
        string relativeUrlWithQueryString,
        string endpointForLogs,
        bool returnNullOnNotFound,
        CancellationToken ct)
    {
        try
        {
            using var req = new HttpRequestMessage(HttpMethod.Get, relativeUrlWithQueryString);
            using var resp = await http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);

            if (returnNullOnNotFound && resp.StatusCode == HttpStatusCode.NotFound)
            {
                return default;
            }

            if (resp.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            {
                _logger.LogWarning(
                    "Ticketmaster ha risposto {StatusCode} su {Endpoint}",
                    (int)resp.StatusCode,
                    endpointForLogs);
                throw new TicketmasterUpstreamAuthException();
            }

            if (!resp.IsSuccessStatusCode)
            {
                _logger.LogWarning(
                    "Ticketmaster ha risposto {StatusCode} su {Endpoint}",
                    (int)resp.StatusCode,
                    endpointForLogs);
                throw new TicketmasterUpstreamHttpException(resp.StatusCode);
            }

            try
            {
                return await resp.Content.ReadFromJsonAsync<T>(_jsonOptions, ct);
            }
            catch (JsonException je)
            {
                _logger.LogWarning(
                    "Risposta Ticketmaster non valida su {Endpoint} ({ErrorType})",
                    endpointForLogs,
                    je.GetType().Name);
                throw new TicketmasterUpstreamProtocolException("Risposta JSON non valida da Ticketmaster.");
            }
        }
        catch (TaskCanceledException) when (!ct.IsCancellationRequested)
        {
            _logger.LogWarning("Timeout contattando Ticketmaster su {Endpoint}", endpointForLogs);
            throw new TicketmasterUpstreamUnavailableException();
        }
        catch (HttpRequestException ex) when (ex.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
        {
            _logger.LogWarning(
                "Ticketmaster ha risposto {StatusCode} su {Endpoint}",
                ex.StatusCode is null ? 0 : (int)ex.StatusCode.Value,
                endpointForLogs);
            throw new TicketmasterUpstreamAuthException();
        }
        catch (HttpRequestException ex) when (ex.StatusCode is null)
        {
            _logger.LogWarning(
                "Errore rete contattando Ticketmaster su {Endpoint} ({ErrorType})",
                endpointForLogs,
                ex.GetType().Name);
            throw new TicketmasterUpstreamUnavailableException();
        }
        catch (HttpRequestException ex)
        {
            var status = ex.StatusCode ?? HttpStatusCode.BadGateway;
            _logger.LogWarning(
                "Ticketmaster ha generato un errore HTTP {StatusCode} su {Endpoint}",
                (int)status,
                endpointForLogs);
            throw new TicketmasterUpstreamHttpException(status);
        }
    }

    private static TicketmasterEventListItem? MapListItem(TicketmasterEventRaw e)
    {
        if (string.IsNullOrWhiteSpace(e.id) || string.IsNullOrWhiteSpace(e.name))
        {
            return null;
        }

        var venue = e._embedded?.venues?.FirstOrDefault();
        var city = venue?.city?.name;
        var venueName = venue?.name;
        var imageUrl = PickBestImageUrl(e.images);
        var localDate = e.dates?.start?.localDate;
        var localTime = e.dates?.start?.localTime;
        var genre = e.classifications?.FirstOrDefault()?.genre?.name;

        return new TicketmasterEventListItem(
            Id: e.id,
            Name: e.name,
            LocalDate: localDate,
            LocalTime: localTime,
            City: city,
            Venue: venueName,
            ImageUrl: imageUrl,
            Url: e.url,
            Genre: genre
        );
    }

    private static TicketmasterEventDetail MapDetail(TicketmasterEventRaw e)
    {
        var venue = e._embedded?.venues?.FirstOrDefault();
        var city = venue?.city?.name;
        var venueName = venue?.name;
        var address = venue?.address?.line1;
        var imageUrl = PickBestImageUrl(e.images);
        var localDate = e.dates?.start?.localDate;
        var localTime = e.dates?.start?.localTime;

        var prices = (e.priceRanges ?? [])
            .Select(p => new TicketmasterPriceRange(p.min, p.max, p.currency))
            .ToList();

        return new TicketmasterEventDetail(
            Id: e.id ?? "",
            Name: e.name ?? "",
            Description: e.info ?? e.pleaseNote,
            LocalDate: localDate,
            LocalTime: localTime,
            City: city,
            Venue: venueName,
            Address: address,
            ImageUrl: imageUrl,
            Url: e.url,
            Prices: prices
        );
    }

    private static string? PickBestImageUrl(List<TicketmasterImageRaw>? images)
    {
        if (images is null || images.Count == 0)
        {
            return null;
        }

        return images
            .OrderByDescending(i => string.Equals(i.ratio, "16_9", StringComparison.OrdinalIgnoreCase))
            .ThenByDescending(i => i.width)
            .Select(i => i.url)
            .FirstOrDefault(u => !string.IsNullOrWhiteSpace(u));
    }

    private static int Clamp(int value, int min, int max) => Math.Min(max, Math.Max(min, value));

    private static string BuildQueryString(params (string Key, string? Value)[] items)
    {
        var parts = items
            .Where(i => !string.IsNullOrWhiteSpace(i.Value))
            .Select(i => $"{Uri.EscapeDataString(i.Key)}={Uri.EscapeDataString(i.Value!)}")
            .ToArray();

        return parts.Length == 0 ? "" : "?" + string.Join("&", parts);
    }

    public sealed record TicketmasterEventsQuery(
        string? Keyword,
        string? City,
        string? ClassificationName,
        DateTimeOffset? StartDateTime,
        DateTimeOffset? EndDateTime,
        string? LatLong = null,
        int? Radius = null,
        string Unit = "km",
        int Page = 0,
        int Size = 12,
        string Sort = "date,asc",
        string CountryCode = "IT",
        string Locale = "it"
    );

    public sealed record PagedResult<T>(
        IReadOnlyList<T> Items,
        int Page,
        int Size,
        int TotalPages,
        long TotalItems
    );

    public sealed record TicketmasterEventListItem(
        string Id,
        string Name,
        string? LocalDate,
        string? LocalTime,
        string? City,
        string? Venue,
        string? ImageUrl,
        string? Url,
        string? Genre
    );

    public sealed record TicketmasterEventDetail(
        string Id,
        string Name,
        string? Description,
        string? LocalDate,
        string? LocalTime,
        string? City,
        string? Venue,
        string? Address,
        string? ImageUrl,
        string? Url,
        IReadOnlyList<TicketmasterPriceRange> Prices
    );

    public sealed record TicketmasterPriceRange(decimal? Min, decimal? Max, string? Currency);

    private sealed class TicketmasterSearchRaw
    {
        public TicketmasterEmbeddedRaw? _embedded { get; set; }
        public TicketmasterPageRaw? page { get; set; }
    }

    private sealed class TicketmasterEmbeddedRaw
    {
        public List<TicketmasterEventRaw>? events { get; set; }
    }

    private sealed class TicketmasterPageRaw
    {
        public int size { get; set; }
        public int totalElements { get; set; }
        public int totalPages { get; set; }
        public int number { get; set; }
    }

    private sealed class TicketmasterEventRaw
    {
        public string? id { get; set; }
        public string? name { get; set; }
        public string? url { get; set; }
        public string? info { get; set; }
        public string? pleaseNote { get; set; }

        public TicketmasterDatesRaw? dates { get; set; }
        public List<TicketmasterImageRaw>? images { get; set; }
        public TicketmasterEventEmbeddedRaw? _embedded { get; set; }
        public List<TicketmasterClassificationRaw>? classifications { get; set; }
        public List<TicketmasterPriceRangeRaw>? priceRanges { get; set; }
    }

    private sealed class TicketmasterDatesRaw
    {
        public TicketmasterStartRaw? start { get; set; }
    }

    private sealed class TicketmasterStartRaw
    {
        public string? localDate { get; set; }
        public string? localTime { get; set; }
    }

    private sealed class TicketmasterImageRaw
    {
        public string? url { get; set; }
        public int width { get; set; }
        public int height { get; set; }
        public string? ratio { get; set; }
    }

    private sealed class TicketmasterEventEmbeddedRaw
    {
        public List<TicketmasterVenueRaw>? venues { get; set; }
    }

    private sealed class TicketmasterVenueRaw
    {
        public string? name { get; set; }
        public TicketmasterCityRaw? city { get; set; }
        public TicketmasterAddressRaw? address { get; set; }
    }

    private sealed class TicketmasterCityRaw
    {
        public string? name { get; set; }
    }

    private sealed class TicketmasterAddressRaw
    {
        public string? line1 { get; set; }
    }

    private sealed class TicketmasterClassificationRaw
    {
        public TicketmasterGenreRaw? genre { get; set; }
    }

    private sealed class TicketmasterGenreRaw
    {
        public string? name { get; set; }
    }

    private sealed class TicketmasterPriceRangeRaw
    {
        [JsonPropertyName("min")]
        public decimal? min { get; set; }

        [JsonPropertyName("max")]
        public decimal? max { get; set; }

        [JsonPropertyName("currency")]
        public string? currency { get; set; }
    }

    public abstract class TicketmasterUpstreamException : Exception
    {
        protected TicketmasterUpstreamException(string message) : base(message) { }
    }

    public sealed class TicketmasterUpstreamAuthException : TicketmasterUpstreamException
    {
        public TicketmasterUpstreamAuthException() : base("ApiKey non valida.") { }
    }

    public sealed class TicketmasterUpstreamUnavailableException : TicketmasterUpstreamException
    {
        public TicketmasterUpstreamUnavailableException() : base("Servizio Ticketmaster non disponibile.") { }
    }

    public sealed class TicketmasterUpstreamHttpException : TicketmasterUpstreamException
    {
        public HttpStatusCode StatusCode { get; }
        public TicketmasterUpstreamHttpException(HttpStatusCode statusCode)
            : base($"Errore Ticketmaster (HTTP {(int)statusCode}).")
        {
            StatusCode = statusCode;
        }
    }

    public sealed class TicketmasterUpstreamProtocolException : TicketmasterUpstreamException
    {
        public TicketmasterUpstreamProtocolException(string message) : base(message) { }
    }
}
