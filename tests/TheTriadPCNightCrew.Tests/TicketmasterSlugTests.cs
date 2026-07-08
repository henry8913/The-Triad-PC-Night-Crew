using TheTriadPCNightCrew.Services;

namespace TheTriadPCNightCrew.Tests;

public sealed class TicketmasterSlugTests
{
    [Theory]
    [InlineData("Hello World", "123", "hello-world--123")]
    [InlineData("Caffè", "abc", "caffe--abc")]
    [InlineData("Event: Techno Night!", "xyz", "event-techno-night--xyz")]
    [InlineData("", "id123", "event--id123")]
    [InlineData("Test", "", "test")]
    [InlineData("  Spaces  ", "99", "spaces--99")]
    public void Build_WithNameAndId_ProducesCorrectSlug(string name, string id, string expected)
    {
        var result = TicketmasterSlug.Build(name, id);
        Assert.Equal(expected, result);
    }

    [Theory]
    [InlineData("hello-world--abc123", true, "abc123")]
    [InlineData("hello-world", false, "")]
    [InlineData("justtext", false, "")]
    [InlineData("", false, "")]
    [InlineData("tm-ZkV1f2GQHp4S", true, "ZkV1f2GQHp4S")]
    [InlineData("event-name--ZkV1f2GQHp4S", true, "ZkV1f2GQHp4S")]
    [InlineData("event-name-ZkV1f2GQHp4S", true, "ZkV1f2GQHp4S")]
    public void TryExtractId_ExtractsCorrectly(string slug, bool expectedSuccess, string expectedId)
    {
        var success = TicketmasterSlug.TryExtractId(slug, out var id);
        Assert.Equal(expectedSuccess, success);
        Assert.Equal(expectedId, id);
    }

    [Theory]
    [InlineData("Hello World", "hello-world")]
    [InlineData("Caffè", "caffe")]
    [InlineData("Event: Techno Night!", "event-techno-night")]
    [InlineData("  Spaces  ", "spaces")]
    [InlineData("", "event")]
    [InlineData("   ", "event")]
    [InlineData("a---b", "a-b")]
    [InlineData("test__double", "test-double")]
    public void Slugify_ProducesCorrectSlug(string input, string expected)
    {
        var result = TicketmasterSlug.Slugify(input);
        Assert.Equal(expected, result);
    }
}
