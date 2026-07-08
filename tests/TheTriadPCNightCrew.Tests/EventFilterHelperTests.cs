using TheTriadPCNightCrew.Services;

namespace TheTriadPCNightCrew.Tests;

public sealed class EventFilterHelperTests
{
    [Theory]
    [InlineData("2025-12-25", "20:00", "2025-12-25 · 20:00")]
    [InlineData("2025-12-25", null, "2025-12-25")]
    [InlineData("2025-12-25", "", "2025-12-25")]
    [InlineData(null, "20:00", "Data da confermare")]
    [InlineData("", "20:00", "Data da confermare")]
    public void FormatDateTime_ReturnsExpected(string? date, string? time, string expected)
    {
        var result = EventFilterHelper.FormatDateTime(date, time);
        Assert.Equal(expected, result);
    }

    [Theory]
    [InlineData("The Venue", "123 Main St", "Milan", "The Venue · 123 Main St · Milan")]
    [InlineData("The Venue", null, "Milan", "The Venue · Milan")]
    [InlineData("The Venue", "123 Main St", null, "The Venue · 123 Main St")]
    [InlineData("The Venue", null, null, "The Venue")]
    [InlineData(null, null, null, "Da confermare")]
    [InlineData(null, "123 Main St", "Milan", "123 Main St · Milan")]
    [InlineData(null, null, "Milan", "Milan")]
    public void FormatVenueLine_ReturnsExpected(string? venue, string? address, string? city, string expected)
    {
        var result = EventFilterHelper.FormatVenueLine(venue, address, city);
        Assert.Equal(expected, result);
    }

    [Fact]
    public void BuildDateRangeUtc_WithWhenAll_ReturnsNulls()
    {
        var (start, end) = EventFilterHelper.BuildDateRangeUtc(WhenFilter.All);
        Assert.Null(start);
        Assert.Null(end);
    }

    [Fact]
    public void BuildDateRangeUtc_WithWhenToday_ReturnsTodayRange()
    {
        var (start, end) = EventFilterHelper.BuildDateRangeUtc(WhenFilter.Today);
        Assert.NotNull(start);
        Assert.NotNull(end);
        var now = DateTimeOffset.UtcNow;
        Assert.True(start <= now.AddDays(1));
        Assert.True(end > now);
    }

    [Fact]
    public void BuildDateRangeUtc_WithWhenWeekend_ReturnsWeekendRange()
    {
        var (start, end) = EventFilterHelper.BuildDateRangeUtc(WhenFilter.Weekend);
        Assert.NotNull(start);
        Assert.NotNull(end);
        Assert.True(end > start);
    }

    [Fact]
    public void BuildDateRangeUtc_WithWhenThisWeek_ReturnsWeekRange()
    {
        var (start, end) = EventFilterHelper.BuildDateRangeUtc(WhenFilter.ThisWeek);
        Assert.NotNull(start);
        Assert.NotNull(end);
        var diff = end.Value - start.Value;
        Assert.True(diff.TotalDays > 6 && diff.TotalDays < 8);
    }

    [Theory]
    [InlineData(null, "Errore nel caricamento del feed (200). Riprova tra poco.")]
    [InlineData("{\"detail\":\"Errore API\"}", "Errore API")]
    [InlineData("{\"title\":\"Bad Request\"}", "Bad Request")]
    public void TryParseProblemDetails_And_BuildUserFriendlyError_ProducesExpected(string? json, string expectedMessage)
    {
        var problem = EventFilterHelper.TryParseProblemDetails(json);
        var result = EventFilterHelper.BuildUserFriendlyError(problem, System.Net.HttpStatusCode.OK);
        Assert.Equal(expectedMessage, result);
    }

    [Fact]
    public void TryParseProblemDetails_WithInvalidJson_ReturnsNull()
    {
        var result = EventFilterHelper.TryParseProblemDetails("not json");
        Assert.Null(result);
    }
}
