using System.Collections.Generic;
using System.Linq;

namespace TheTriadPCNightCrew.Services;

public record Article(
    string Slug,
    string Category,
    string Title,
    string Excerpt,
    string Date,
    int ReadTime,
    string ImageUrl,
    string ContentHtml);

public static class ArticleStore
{
    public static readonly IReadOnlyList<Article> Articles = new List<Article>
    {
        new(
            "secret-bar-emilia-romagna",
            "In Evidenza",
            "I 5 Secret Bar migliori dell'Emilia Romagna",
            "Da Piacenza a Bologna, i cocktail bar che non trovi su Google Maps. Parola d'ordine e porte nascoste nei retrobottega.",
            "15 Settembre",
            7,
            "images/unsplash/mag-1.jpg",
            """
            <p class="lead mb-4">L'Emilia Romagna non è solo osterie e balere. Negli ultimi anni, la scena della mixology si è arricchita di locali segreti (speakeasy) dove per entrare serve una parola d'ordine o risolvere un enigma.</p>
            
            <h3 class="fw-semibold mt-5 mb-3">1. Il Salotto Nascosto (Piacenza)</h3>
            <p>Situato dietro la finta libreria di un bar del centro, questo locale offre un'atmosfera anni '20. I cocktail sono preparati con distillati artigianali e sciroppi fatti in casa. Provate il loro Old Fashioned affumicato al legno di ciliegio.</p>
            
            <h3 class="fw-semibold mt-5 mb-3">2. La Stanza di Vetro (Bologna)</h3>
            <p>Per trovare l'ingresso dovete cercare una vecchia cabina telefonica in via Pratello. Componete il numero giusto e la parete si aprirà. All'interno, velluto rosso e jazz dal vivo creano un'atmosfera perfetta per appuntamenti eleganti.</p>

            <h3 class="fw-semibold mt-5 mb-3">3. Alchimia (Parma)</h3>
            <p>Dietro la porta di un'apparente tintoria, si nasconde uno dei laboratori di mixology più avanzati della regione. I bartender usano centrifughe e distillatori sottovuoto per creare drink che sembrano pozioni magiche.</p>
            
            <h3 class="fw-semibold mt-5 mb-3">4. Il Sarto (Reggio Emilia)</h3>
            <p>Dovrete portare un "tessuto" (un campione di stoffa che vi daranno al momento della prenotazione online) per convincere il finto sarto a farvi passare nel retro. La drink list cambia ogni mese ed è ispirata alle grandi epoche della moda.</p>
            
            <h3 class="fw-semibold mt-5 mb-3">5. La Cassaforte (Modena)</h3>
            <p>Nascosto nel caveau di una vecchia banca dismessa. L'acustica è incredibile e i drink sono serviti in bicchieri di cristallo lavorato a mano. Non c'è menu: dite al bartender cosa vi piace e lui creerà qualcosa su misura per voi.</p>
            """
        ),
        new(
            "techno-cantina-basement-ritual",
            "Intervista",
            "La Techno non è morta, è tornata in cantina",
            "Quattro chiacchiere con il fondatore del Basement Ritual su come i veri club stiano tornando alle origini: no foto, solo casse dritte.",
            "12 Agosto",
            4,
            "images/unsplash/mag-2.jpg",
            """
            <p class="lead mb-4">Abbiamo incontrato Marco, il fondatore del collettivo <em>Basement Ritual</em>, per capire perché sempre più party techno vietano i telefoni in pista e tornano a suonare in spazi piccoli e crudi.</p>
            
            <p><strong>The Triad PC:</strong> Marco, da dove nasce l'esigenza di tornare in cantina?</p>
            <p><strong>Marco:</strong> "I grandi club sono diventati teatri. La gente va per fare le storie su Instagram, non per ballare. Abbiamo perso la connessione con la musica e con chi ci sta di fianco. Tornare in cantina significa eliminare le distrazioni: luci al minimo, niente palchi giganti, solo un buon impianto e la cassa dritta."</p>

            <p><strong>The Triad PC:</strong> La regola del 'No Photos' sta diventando uno standard. Perché?</p>
            <p><strong>Marco:</strong> "È una questione di libertà. Se sai che nessuno ti sta riprendendo, balli in modo diverso. Ti lasci andare. È lo spirito originario della club culture, quello che c'era prima dei social media. E poi, onestamente, vedere una pista illuminata dagli schermi dei telefoni ammazza completamente il mood."</p>

            <p><strong>The Triad PC:</strong> Cosa rispondi a chi dice che è una mossa elitaria?</p>
            <p><strong>Marco:</strong> "Non è elitaria, è protettiva. Non selezioniamo la gente in base a come si veste, ma in base all'attitudine. Se vieni per la musica, sei il benvenuto. Se vieni per farti i selfie, ci sono mille altri posti perfetti per quello."</p>
            """
        ),
        new(
            "cocktail-autunno-milano",
            "Guida",
            "Cosa bere stanotte: I signature cocktail dell'autunno",
            "Neon arancio e bicchieri affumicati. Abbiamo provato (e valutato) le nuove drink list dei locali milanesi per farvi andare a colpo sicuro.",
            "10 Luglio",
            6,
            "images/unsplash/mag-3.jpg",
            """
            <p class="lead mb-4">L'autunno a Milano porta con sé nuove drink list. Addio spritz annacquati e drink tropicali, benvenuti sapori intensi, spezie e fumo. Ecco la nostra top 3.</p>

            <h3 class="fw-semibold mt-5 mb-3">1. 'Smoked Negroni' al Neon Club</h3>
            <p>Un classico rivisitato. Servito in una teca di vetro piena di fumo di legno di quercia. Il sapore è rotondo, perfetto per iniziare la serata. Voto: 9/10.</p>

            <h3 class="fw-semibold mt-5 mb-3">2. 'Pumpkin Spice Mule' al The Warehouse</h3>
            <p>Un Moscow Mule autunnale. Vodka infusa alla zucca e cannella, ginger beer artigianale e una spolverata di noce moscata. Sorprendentemente fresco. Voto: 8.5/10.</p>

            <h3 class="fw-semibold mt-5 mb-3">3. 'Black Velvet' al Dark Room</h3>
            <p>Un drink nerissimo a base di Gin, liquore alla mora, carbone attivo e un tocco di lime. Elegante, misterioso e molto instagrammabile (anche se al Dark Room le foto non si fanno). Voto: 8/10.</p>
            """
        ),
        new(
            "milano-fashion-week-party-accessibili",
            "Reportage",
            "Milano Fashion Week: I party accessibili (se sai come)",
            "Non serve per forza un pass VIP per fare serata durante la settimana della moda. Ecco i locali dove l'ingresso è libero e la musica è curata.",
            "28 Giugno",
            5,
            "images/unsplash/venue-hero.jpg",
            """
            <p class="lead mb-4">La MFW può sembrare un fortino inespugnabile, ma la vera festa spesso si sposta nei locali off-circuit. Ecco dove andare per ballare senza dover superare tre selezioni all'ingresso.</p>

            <p><strong>Il trucco è evitare i soliti nomi.</strong> Durante la Fashion Week, i mega-club sono inavvicinabili. Ma i piccoli bar, i club underground e gli spazi post-industriali in zone come Bovisa o Lambrate si riempiono di addetti ai lavori che vogliono solo rilassarsi dopo ore di sfilate.</p>

            <p>Tenete d'occhio le pagine Instagram dei collettivi indipendenti. Spesso annunciano "secret party" il giorno stesso. L'ingresso è quasi sempre libero o con una fee minima, ma la qualità musicale è altissima, spesso con DJ internazionali che suonano set non annunciati.</p>
            """
        ),
        new(
            "gabo-ai-dietro-le-quinte",
            "Dietro le quinte",
            "Gabo AI: Come The Triad ha addestrato un buttafuori digitale",
            "Il nostro tech lead racconta i mesi passati ad ascoltare PR e organizzatori per creare un chatbot che capisce davvero cosa vuol dire 'far serata'.",
            "15 Maggio",
            8,
            "images/unsplash/team-3.jpg",
            """
            <p class="lead mb-4">Gabo non è un chatbot normale. Non risponde "Mi dispiace, non ho capito". Risponde "Bro, stasera la techno spinge al locale X". Ecco come lo abbiamo creato.</p>

            <p>Siamo partiti da un'idea semplice: le persone non cercano "eventi musicali dalle 23:00". Cercano "qualcosa per fare after" o "un posto tranquillo per bere bene". Abbiamo dovuto insegnare all'AI il linguaggio della notte.</p>

            <p>Per mesi, abbiamo raccolto migliaia di messaggi vocali, chat di gruppi WhatsApp e conversazioni con PR e buttafuori. Abbiamo mappato concetti come <em>'vibe'</em>, <em>'serata pettinata'</em>, <em>'cassa dritta'</em> e li abbiamo tradotti in parametri di ricerca per il nostro database.</p>

            <p>Il risultato? Gabo capisce il contesto. Se gli scrivi "stasera piove, voglio stare al caldo con della buona musica", non ti propone una discoteca all'aperto, ma un jazz club intimo. È questo il vero salto di qualità per The Triad PC.</p>
            """
        )
    };

    public static Article? GetBySlug(string slug) => Articles.FirstOrDefault(a => a.Slug == slug);
}
