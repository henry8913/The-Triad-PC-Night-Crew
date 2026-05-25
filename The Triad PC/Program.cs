using TheTriadPCNightCrew.Components;
using TheTriadPCNightCrew.Services;
using static TheTriadPCNightCrew.Services.TicketmasterApi;

var dotenvLoaded = TheTriadPCNightCrew.DotEnv.LoadFromCwdIfPresent();

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

builder.Services.AddHttpClient();
builder.Services.AddMemoryCache();
builder.Services.AddHttpClient("Ticketmaster", (sp, client) =>
{
    var cfg = sp.GetRequiredService<IConfiguration>();
    var baseUrl = cfg["Ticketmaster:BaseUrl"] ?? "https://app.ticketmaster.com/discovery/v2/";
    client.BaseAddress = new Uri(baseUrl, UriKind.Absolute);
    client.Timeout = TimeSpan.FromSeconds(cfg.GetValue<int?>("Ticketmaster:TimeoutSeconds") ?? 10);
});

builder.Services.AddSingleton<TicketmasterApi>();

var app = builder.Build();

if (dotenvLoaded > 0)
{
    app.Logger.LogInformation("DotEnv: caricate {Count} variabili da .env (solo se mancanti).", dotenvLoaded);
}

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}
app.UseStatusCodePagesWithReExecute("/not-found", createScopeForStatusCodePages: true);
app.UseHttpsRedirection();

app.UseAntiforgery();

app.MapStaticAssets();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

var api = app.MapGroup("/api");
var tm = api.MapGroup("/ticketmaster");

tm.MapGet("/events", async ([AsParameters] TicketmasterEventsQuery query, TicketmasterApi ticketmaster, CancellationToken ct) =>
{
    try
    {
        var result = await ticketmaster.SearchEventsAsync(query, ct);
        return Results.Ok(result);
    }
    catch (TicketmasterUpstreamAuthException)
    {
        return Results.Problem(statusCode: 502, title: "Ticketmaster", detail: "ApiKey non valida");
    }
    catch (TicketmasterUpstreamHttpException ex) when (ex.StatusCode == System.Net.HttpStatusCode.BadRequest)
    {
        var page = Math.Max(0, query.Page);
        var size = Math.Min(200, Math.Max(1, query.Size));
        return Results.Ok(new PagedResult<TicketmasterEventListItem>([], page, size, 0, 0));
    }
    catch (TicketmasterUpstreamHttpException ex) when (ex.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
    {
        return Results.Problem(statusCode: 503, title: "Ticketmaster", detail: "Rate limit Ticketmaster. Riprova tra poco.");
    }
    catch (TicketmasterUpstreamHttpException ex)
    {
        return Results.Problem(statusCode: 502, title: "Ticketmaster", detail: $"Errore Ticketmaster (HTTP {(int)ex.StatusCode}).");
    }
    catch (TicketmasterUpstreamUnavailableException)
    {
        return Results.Problem(statusCode: 503, title: "Ticketmaster", detail: "Servizio Ticketmaster non disponibile");
    }
    catch (TicketmasterUpstreamException)
    {
        return Results.Problem(statusCode: 502, title: "Ticketmaster", detail: "Errore dal servizio Ticketmaster");
    }
    catch (InvalidOperationException)
    {
        return Results.Problem(statusCode: 500, title: "Ticketmaster", detail: "Configurazione Ticketmaster mancante");
    }
});

tm.MapGet("/events/{id}", async (string id, TicketmasterApi ticketmaster, CancellationToken ct) =>
{
    try
    {
        var evt = await ticketmaster.GetEventAsync(id, ct);
        return evt is null ? Results.NotFound() : Results.Ok(evt);
    }
    catch (TicketmasterUpstreamAuthException)
    {
        return Results.Problem(statusCode: 502, title: "Ticketmaster", detail: "ApiKey non valida");
    }
    catch (TicketmasterUpstreamHttpException ex) when (ex.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
    {
        return Results.Problem(statusCode: 503, title: "Ticketmaster", detail: "Rate limit Ticketmaster. Riprova tra poco.");
    }
    catch (TicketmasterUpstreamHttpException ex)
    {
        return Results.Problem(statusCode: 502, title: "Ticketmaster", detail: $"Errore Ticketmaster (HTTP {(int)ex.StatusCode}).");
    }
    catch (TicketmasterUpstreamUnavailableException)
    {
        return Results.Problem(statusCode: 503, title: "Ticketmaster", detail: "Servizio Ticketmaster non disponibile");
    }
    catch (TicketmasterUpstreamException)
    {
        return Results.Problem(statusCode: 502, title: "Ticketmaster", detail: "Errore dal servizio Ticketmaster");
    }
    catch (InvalidOperationException)
    {
        return Results.Problem(statusCode: 500, title: "Ticketmaster", detail: "Configurazione Ticketmaster mancante");
    }
});

app.MapPost("/chat", async (HttpRequest request, IHttpClientFactory httpClientFactory, IConfiguration cfg, CancellationToken ct) =>
{
    var target = cfg["CHAT_API_URL"] ?? cfg["Chat:ApiUrl"];
    if (string.IsNullOrWhiteSpace(target))
    {
        return Results.Problem(
            title: "CHAT_API_URL mancante",
            detail: "Imposta env var CHAT_API_URL oppure Chat:ApiUrl in appsettings.");
    }

    var body = await new StreamReader(request.Body).ReadToEndAsync(ct);
    var mediaType = "application/json";
    if (!string.IsNullOrWhiteSpace(request.ContentType) &&
        System.Net.Http.Headers.MediaTypeHeaderValue.TryParse(request.ContentType, out var parsed) &&
        !string.IsNullOrWhiteSpace(parsed.MediaType))
    {
        mediaType = parsed.MediaType!;
    }

    using var forward = new HttpRequestMessage(HttpMethod.Post, target)
    {
        Content = new StringContent(body, System.Text.Encoding.UTF8, mediaType)
    };

    var apiKey = cfg["CHAT_API_KEY"] ?? cfg["Chat:ApiKey"];
    var apiKeyHeader = cfg["Chat:ApiKeyHeader"] ?? "Authorization";
    if (!string.IsNullOrWhiteSpace(apiKey))
    {
        if (string.Equals(apiKeyHeader, "Authorization", StringComparison.OrdinalIgnoreCase) &&
            !apiKey.TrimStart().StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            forward.Headers.TryAddWithoutValidation("Authorization", $"Bearer {apiKey}");
        }
        else
        {
            forward.Headers.TryAddWithoutValidation(apiKeyHeader, apiKey);
        }
    }

    var client = httpClientFactory.CreateClient();
    try
    {
        using var resp = await client.SendAsync(forward, ct);
        var respBody = await resp.Content.ReadAsStringAsync(ct);
        var respContentType = resp.Content.Headers.ContentType?.ToString() ?? "application/json";
        return Results.Content(respBody, respContentType, statusCode: (int)resp.StatusCode);
    }
    catch (TaskCanceledException)
    {
        return Results.Problem(statusCode: 504, title: "Chat", detail: "Timeout contattando il backend chat.");
    }
    catch (HttpRequestException)
    {
        return Results.Problem(statusCode: 502, title: "Chat", detail: "Backend chat non raggiungibile. Avvia Gabo AI e verifica CHAT_API_URL.");
    }
});

app.Run();
