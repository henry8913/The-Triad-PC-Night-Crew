using System.Collections.Generic;
using System.Linq;

namespace TheTriadPCNightCrew.Services;

public record Event(
    string Slug,
    string Category,
    string City,
    string Title,
    string Excerpt,
    string Description,
    string Venue,
    string Address,
    string Date,
    string Time,
    string Price,
    string ImageUrl,
    bool IsFeatured = false);

public static class EventStore
{
    public static readonly IReadOnlyList<Event> Events = new List<Event>
    {
        new(
            "neon-pulse-milano",
            "Club",
            "Milano",
            "Neon Pulse",
            "Warehouse vibes, bassline e luci arancio.",
            "Una notte intera dedicata alla club culture pura. Lascia a casa il telefono, la pista da ballo del Warehouse District si illumina solo di neon arancio. Line-up segreta fino all'apertura delle porte, ma aspettati bassi potenti e ritmi serrati fino all'alba.",
            "Warehouse District",
            "Via Giovanni Battista Pirelli, Milano",
            "Oggi",
            "23:30 - 05:00",
            "da €12",
            "images/unsplash/event-1.jpg",
            true
        ),
        new(
            "jazz-after-dark-milano",
            "Live",
            "Milano",
            "Jazz After Dark",
            "Set intimo, cocktail e luci soffuse.",
            "Un'esperienza immersiva nel cuore del Centro Storico. Un quartetto jazz locale rielabora i grandi classici in chiave contemporanea. Consigliamo di prenotare un tavolo e provare il loro 'Smoked Negroni'.",
            "Centro Storico",
            "Via Brera, Milano",
            "Venerdì",
            "21:30 - 02:00",
            "da €10",
            "images/unsplash/event-2.jpg",
            true
        ),
        new(
            "basement-ritual-piacenza",
            "Techno",
            "Piacenza",
            "Basement Ritual",
            "Underground e zero compromessi.",
            "Il collettivo Basement Ritual torna a Piacenza per il party più crudo del mese. Nessuna prevendita, ingresso solo in lista nominale. Cassa dritta, sudore e techno industriale.",
            "Underground PC",
            "Via Roma, Piacenza",
            "Sabato",
            "00:00 - 06:00",
            "da €15",
            "images/unsplash/event-3.jpg",
            true
        ),
        new(
            "city-lights-bologna",
            "Indie",
            "Bologna",
            "City Lights (Live)",
            "Chitarre, synth e coro finale.",
            "Tre band emergenti della scena indie bolognese si alternano sul palco principale. A seguire, dj set electro-indie per ballare fino a chiusura. Un'ottima occasione per scoprire nuova musica.",
            "Locomotiv Club",
            "Via Sebastiano Serlio, Bologna",
            "Sabato",
            "22:00 - 04:00",
            "da €9",
            "images/unsplash/event-4.jpg",
            false
        ),
        new(
            "late-show-comedy-bologna",
            "Comedy",
            "Bologna",
            "Late Show",
            "Stand-up fino a tardi, senza filtri.",
            "Open mic e comici affermati si passano il microfono in una cantina dal sapore newyorkese. Risate garantite, drink forti e argomenti rigorosamente vietati ai minori.",
            "Comedy Cellar",
            "Via del Pratello, Bologna",
            "Domenica",
            "21:00 - 01:00",
            "Gratis",
            "images/unsplash/city-3.jpg",
            false
        ),
        new(
            "secret-guest-torino",
            "Special",
            "Torino",
            "Secret Guest",
            "Location segreta, reveal last minute.",
            "Un evento esclusivo per soli 100 partecipanti. La location esatta e l'artista verranno comunicati via email 2 ore prima dell'inizio dell'evento a chi ha acquistato il biglietto. Preparatevi a qualcosa di memorabile.",
            "Location Segreta",
            "Torino (Centro)",
            "Prossima settimana",
            "23:00 - ???",
            "da €20",
            "images/unsplash/city-4.jpg",
            false
        )
    };

    public static Event? GetBySlug(string slug) => Events.FirstOrDefault(e => e.Slug == slug);
    public static IEnumerable<Event> GetFeatured() => Events.Where(e => e.IsFeatured);
}
