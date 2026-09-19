# Dendrite: persoonlijke kennisgraph met AI-mentor

**Auteur:** Paul Laurijssens · **Versie 2, september 2026** (vervangt "AI Technology Mentor Platform", augustus 2026)

> **Update 10 september 2026:** de afgesproken vervolgrichting en uitvoering staan
> in [Implementation-plan-v3.md](Implementation-plan-v3.md). Dit v2-document blijft
> de beschrijving van de oorspronkelijke basis. V3 voegt gesprekgestuurde groei,
> gedeelde mentorcontext, terugnavigatie, begrip met bewijs en evoluerend geheugen
> toe aan de route. Voor een tweede lerende is een aparte installatie gekozen.

---

## 1. Wat het is en waarom

Podcasts en papers zitten vol concepten die je niet kent. Ze opzoeken is ongestructureerd, onsamenhangend en kost veel tijd; je vindt een definitie, geen begrip, en vergeet hem weer.

Dendrite draait dat om. Je geeft aan **welke concepten je wilt begrijpen**, een mentor legt ze uit op jouw niveau, splitst uit welke voorkennis je mist, en onthoudt over sessies heen waar je bent. Het resultaat is een groeiende kaart van jouw begrip: wat je hebt gevraagd, wat je nog moet leren, en hoe het samenhangt.

**Doelgroep:** in eerste instantie Paul zelf. De opzet is LLM-agnostisch en per persoon instelbaar (niveau 1 t/m 5), zodat dezelfde app later voor zijn zoon kan dienen. Bredere uitrol is een optie, geen doel.

## 2. Wat er is veranderd ten opzichte van het oorspronkelijke plan

| Oorspronkelijk (aug 2026) | Nu | Waarom |
|---|---|---|
| Bulk-extractie: alles uit een podcast de graph in | **Concept-gedreven**: analyse levert kandidaten, jij kiest wat de kaart in gaat | De graph moet jouw begrip weerspiegelen, niet de inhoud van elke aflevering. Governance aan de poort in plaats van opruimen achteraf. |
| Kennisgatdetectie als losse "unieke innovatie" | Komt vanzelf uit de flow: de mentor benoemt prerequisites, die staan als "suggested" in de graph | Geen apart systeem nodig; de open prerequisites zíjn je kennisgaten. |
| Vijf agents (ingestion, extraction, knowledge, mentor, curriculum) | Drie modules: extractie-pijplijn, mentor-chat, geheugenconsolidatie | Eenvoudiger, toetsbaar, geen orkestratie-overhead. |
| Neo4j + Qdrant + multi-LLM | Neo4j (met vector-index) + LiteLLM | Eén database; modellen wisselen via één regel in `.env`. |
| Dashboard | "De kaart is het thuis": full-screen graph met zwevende UI | De samenhang tussen concepten is het product, dus de graph is het hoofdscherm. |

## 3. Huidige implementatie

### Stack
- **Backend:** FastAPI (Python), LiteLLM als LLM-abstractie
- **Database:** Neo4j 5 Community met GDS en APOC, vector-index op 3072 dimensies
- **Modellen:** `EXTRACT_MODEL` (Gemini Flash, volumewerk) en `MENTOR_MODEL` (Claude Sonnet, gesprekken), embeddings via `gemini-embedding-2-preview`
- **Frontend:** Next.js, react-force-graph-2d, i18n NL/EN
- **Draait:** lokaal via Docker Compose; dezelfde compose-file is bedoeld voor een Hetzner-VPS met Tailscale

### De flow in vier stappen

1. **Invoeren** via de command bar ("Toevoegen +"): een los onderwerp, een geplakt transcript of paper, of een YouTube-URL (transcript wordt automatisch opgehaald, geen account nodig).
2. **Analyseren**: lange bronnen worden op inhoud in chunks van 8-15 minuten geknipt (hoofdstukken als die er zijn, anders een topic-segmentatie), parallel geëxtraheerd, gededupliceerd en gescoord. Concepten die in meer chunks terugkomen wegen zwaarder. Elke kandidaat krijgt citaten met tijdcode ("Spring naar 47:12" opent de video op dat moment). Een 2,5-uurs podcast kost 1-2 minuten en een paar cent.
3. **Kiezen** in het review-paneel: kandidaten als boom van hoofd- en subtopics met checkboxes; wat al in je kaart staat is gemarkeerd. Alleen wat je aanvinkt komt in de graph, met status **"te leren"** (goud). Niets anders wordt opgeslagen.
4. **Leren**: klik op een node en het mentorpaneel opent. "Leg uit" geeft een uitleg op jouw niveau en zet prerequisites als "suggested" in de graph. Daarna chat je door: doorvragen, voorbeeld, overhoring, ander niveau. "Beëindig gesprek" slaat op wat je nu begrijpt (zie hoofdstuk 4).

### Datamodel (kern)
```
(:Concept {name, definition, aliases, status, embedding})
    status: suggested < queued (te leren) < learning < learned
(:Source {title, type, url})          (Concept)-[:MENTIONED_IN {mentions:[{start_sec, quote}]}]->(Source)
(Concept)-[:PREREQUISITE_OF | PART_OF | RELATED_TO]->(Concept)
(:Person {name, level, ui_language, learning_profile})
(Person)-[:UNDERSTANDS {level, covered, struggles, misconceptions, summary, ...}]->(Concept)
(Person)-[:HAD_SESSION]->(:ChatSession)-[:HAS_MESSAGE]->(:ChatMessage)
```

### Graph-gedrag
- Buiten mentor-modus "ademt" de graph zacht en trekt nodes licht naar de cursor; de node onder de muis staat stil zodat klikken raak is.
- In mentor-modus stopt de animatie, de actieve node wordt links gecentreerd, de rest dimt licht maar blijft aanklikbaar.

## 4. Hoe het geheugen werkt (eenvoudig uitgelegd)

Het geheugen heeft drie lagen. Elke laag beantwoordt een andere vraag.

**Laag 1: Wat is er gezegd?**
Elk chatbericht wordt letterlijk opgeslagen als onderdeel van een gesprek over één concept. Dit is de ruwe waarheid: goedkoop, zonder interpretatie, en nooit weggegooid. Als laag 2 of 3 ooit fout of vervuild raakt, wordt hij hieruit opnieuw opgebouwd ("Geheugen opnieuw opbouwen" in het profiel).

**Laag 2: Wat begrijp ik van dit concept?**
Na elk gesprek (bij "Beëindig gesprek", of automatisch na 30 minuten stilte) leest een LLM het gesprek en destilleert per concept: welke aspecten zijn behandeld, waar hapert het, welke misvattingen zijn rechtgezet, hoeveel controlevragen goed en fout gingen, en een samenvatting van "waar zijn we gebleven". Dit staat op de relatie tussen jou en dat concept. Bij een nieuw gesprek over hetzelfde concept, ook weken later of in een nieuw context window, laadt de mentor deze toestand en bouwt voort in plaats van te herhalen ("Vorige keer zagen we... nu...").

**Laag 3: Hoe leer ik?**
Uit dezelfde gesprekken worden observaties over jouw leerstijl gehaald, alleen als het gesprek daar echt bewijs voor geeft: wat werkt (codevoorbeelden, analogieën uit een bepaald domein), wat niet, welke voorkeuren je uitspreekt. Dit staat op jouw persoon, los van concepten, en gaat mee in élk gesprek. Zeg je één keer "ik snap dingen beter met code", dan krijgt elk volgend concept een codevoorbeeld.

**Drie principes die dit betrouwbaar houden**
1. *Ruwe data is waarheid.* Laag 2 en 3 zijn afgeleid en regenereerbaar; laag 1 is heilig.
2. *Inspecteerbaar en corrigeerbaar.* Bovenin het mentorpaneel zie je precies wat het systeem over jouw begrip denkt; elk item kun je met een kruisje verwijderen. Verwijderde observaties komen niet terug, ook niet in andere bewoordingen bij een rebuild (het consolidatiemodel krijgt ze mee als afgewezen).
3. *Eén taal per persoon.* De mentor antwoordt in de taal waarin je hem aanspreekt, maar het geheugen wordt altijd in jouw UI-taal geschreven, zodat het één samenhangend geheel blijft.

Dit patroon (goedkoop loggen, later in een aparte "dream state" consolideren, vooraf berekend geheugen bij sessiestart injecteren) volgt het model uit *Unified Agentic Memory Across Harnesses Using Hooks* (Towards Data Science, mei 2026), aangepast op consolidatie bij sessie-einde in plaats van periodieke batches.

## 5. Kosten

Voor persoonlijk gebruik verwaarloosbaar: een 2,5-uurs podcast analyseren kost enkele centen, een concept leren 1-3 cent, een chatbeurt 1-3 cent, consolidatie ~1 cent. Bij dagelijks gebruik enkele euro's per maand, vrijwel volledig in de mentor-chat. Neo4j draait lokaal gratis.

## 6. Bewust nog niet gebouwd

- **Fase 2 mentor-tools**: de mentor mag zelf de graph bijwerken (begrip markeren, ontbrekende prerequisite toevoegen, niveau bijstellen). Eerst zien hoe de mentor in de praktijk voelt.
- **Profiel voor tweede persoon** (zoon): datamodel is er klaar voor, UI nog niet.
- **VPS-deployment** met Tailscale; dan ook de consolidatie-taak als periodieke job in plaats van bij startup.
- **Web-grounding** voor "Genereer bron over dit onderwerp", zodat LLM-gegenereerd bronmateriaal actueel is.

## 7. Werkwijze die goed bleek

- **Één stap per keer, feedback ertussen.** Elke bouwstap werd eerst door Paul in de praktijk beoordeeld voordat de volgende werd bepaald.
- **Rolverdeling.** Claude (chat) voor architectuur, productbeslissingen en prompts; Claude Code voor implementatie, debugging en browsertests met metingen.
- **Beslissingen met redenering.** Postgres → Neo4j, 1536 → 3072 dimensies, ghost-nodes → review-paneel: telkens gekozen op basis van uitgelegde afwegingen, en teruggedraaid wanneer de praktijk iets anders liet zien.
- **Praktijk boven plan.** De grootste verbeteringen (concept-gedreven flow, review-boom, bedienbare graph in mentor-modus) kwamen uit eigen gebruik, niet uit het oorspronkelijke ontwerp.
