# Dendrite → een mentor die meegroeit

**Versie 3 · 10 september 2026 · Status: goedgekeurde richting, gefaseerde uitvoering**

Dit document volgt op [Dendrite-plan-v2.md](Dendrite-plan-v2.md). Versie 2
beschrijft de bestaande basis; dit document is de actuele implementatieroute.
Niet alle onderstaande functies zijn al gebouwd. De voortgang onderaan is
leidend. Paul heeft op 12 september bevestigd dat de bestaande Neo4j-data de
initiële dataset is: behouden en verder uitbouwen. Er is geen reset gepland.

## Productrichting

Het gesprek stuurt het leren en de kenniskaart. De mentor bouwt voort op wat
eerder besproken is, stelt zinvolle zijpaden voor en helpt terug te keren naar
de oorspronkelijke vraag. De kaart maakt de samenhang zichtbaar en bewaart
bewuste keuzes; een gesprek hoeft niet met een klik op een node te beginnen.

**Trellis** is een mogelijke nieuwe naam: een rek waarlangs klimplanten groeien.
Het beeld past bij ondersteuning en structuur voor groeiende kennis. De naam
is nog geen besluit tot hernoemen; beschikbaarheid is niet onderzocht.

Eén installatie blijft voor één lerende. Voor Pauls zoon komt een afzonderlijke
installatie met eigen database en instellingen. Multi-user accounts, gedeelde
voortgang en een profielselector vallen daarom buiten deze route.

## Beslissingen

- Leerintentie, aangetoonde vaardigheid en recentheid zijn verschillende dingen.
  `covered` is besproken stof, geen bewijs van beheersing. Zelfbeoordeling blijft
  mogelijk en zichtbaar naast bewijs uit gesprekken.
- Misvattingen en moeitepunten kunnen opgelost of achterhaald zijn. Bewaar hun
  geschiedenis, maar behandel ze dan niet langer als actuele problemen.
  Begrepen concepten verdwijnen niet van de kaart.
- Uitleg en chat delen dezelfde persoonlijke context. Een lerende mag expliciet
  om een uitleg vanaf nul vragen; standaard bouwt de mentor voort.
- Voorstellen uit gesprekken worden zichtbaar vóór ze concepten of relaties
  aanmaken. Verkennen of bewaren accepteert een voorstel; afwijzen doet dat niet.
- Zijpaden bewaren een terugweg naar het eerdere concept en gesprek.
- Leerprofielobservaties krijgen bewijs en ruimte voor verandering. Een voorkeur
  uit één context is niet automatisch een permanente eigenschap.
- Ouderlijke instellingen zijn leesbaar en transparant. Een systeeminstructie
  is niet de enige maatregel voor betrouwbare grenzen of meldingen.

## Fase 1 — Doorlopend, actief gesprek

### 1A. Gedeelde context en betrouwbaar consolideren

Uitleg gebruikt begripstoestand, leerprofiel, bestaande broncontext en recente
berichten van het actieve gesprek. Ook een nieuw concept krijgt het leerprofiel
mee. Houd de canonieke definitie neutraal; personalisatie hoort in de uitleg.
Leg niet zonder bewijs vast dat besproken stof beheerst wordt.

Consolidatie onderscheidt een gesprek zonder leerlinginvoer van een mislukte
modelaanroep. Alleen het eerste mag zonder geheugenupdate worden afgesloten;
een mislukking blijft beschikbaar voor een volgende poging.

Acceptatie:
- Een uitleg na een eerder gesprek gebruikt de eerdere moeilijkheden en context.
- Een nieuw onderwerp gebruikt bestaande voorkeuren zonder conceptgeheugen te
  verzinnen.
- Een modelstoring verliest geen bericht en sluit consolidatie niet als geslaagd af.
- Controle met gemockte database en modellen; geen betaalde calls in unit tests.

### 1B. Voorstellen in het gesprek

De mentor kan maximaal drie relevante concepten voorstellen na een antwoord,
ook wanneer de lerende zelf om een onderwerp vraagt. Elk voorstel bevat een
naam, definitie, reden en de relatie met het huidige concept. De UI biedt
**Verkennen**, **Bewaar voor later** en **Afwijzen**. Modeluitvoer wordt gevalideerd;
een voorstel heeft geen bevoegdheid om zelfstandig de kaart te wijzigen.

Bewaar voorstellen bij hun gesprek met status pending/queued/explored/dismissed,
zodat herladen of afsluiten geen tweede acceptatie vereist. Acceptatie hergebruikt
canonieke concepten, maakt geen fictieve bron aan en is herhaalbaar zonder
duplicaten. Relatierichting is expliciet: bijvoorbeeld het voorgestelde
voorkennisconcept is `PREREQUISITE_OF` het huidige concept.

Acceptatie:
- Een afgewezen of onbeantwoord voorstel maakt geen Concept of conceptrelatie.
- Bewaren voegt toe als `queued` zonder een sterkere bestaande status te verlagen.
- Verkennen opent het canonieke concept; een uitleg volgt via de bestaande leerflow.
- Dubbel klikken/herhalen dupliceert geen conceptrelatie.
- Fouten in voorstelgeneratie verhinderen niet dat het mentorantwoord behouden blijft.
- Verzoeken mogen alleen voorstellen voor de betreffende persoon behandelen.

**Bestaande uitzondering:** `/learn` schrijft voorlopig nog automatisch
voorkennis als `suggested`. Het overbrengen van deze oudere route naar dezelfde
acceptatieflow volgt na beoordeling van de nieuwe gesprekskaarten.

### 1C. Terugweg uit zijpaden

Een zichtbaar pad toont de bezochte concepten binnen de leersessie. Vanuit een
voorstel of de mini-boom kan de lerende een zijpad openen en terugkeren, zonder
het eerdere gesprek te beëindigen. De oorspronkelijke vraag blijft in de log.
Navigatie herstelt het gesprek en het gekozen niveau. Bewaar het pad per browsertab
voor herladen; de database blijft de waarheid voor de gesprekken zelf.

Acceptatie:
- A → B → C → terug naar A heropent A en snoeit het pad tot A.
- Een cyclus A → B → A maakt geen eindeloze breadcrumb.
- Een snelle wissel van concept laat geen laat antwoord in het verkeerde paneel zien.
- Kaarten en navigatie werken in Nederlands/Engels en in compact/volledig scherm.

## Fase 2 — Begrip met bewijs en veranderend geheugen

Splits de huidige status geleidelijk, zonder een database-reset:

| Onderdeel | Voorstel | Betekenis |
|---|---|---|
| Intentie | interested / queued / learning | Wat wil ik oppakken? |
| Zelfbeoordeling | eigen inschatting + datum | Wat denk ik zelf te begrijpen? |
| Bewijs | explain / apply / connect + sessie/bericht + datum | Wat liet ik zien? |
| Observatie | active / resolved / superseded | Is dit moeitepunt nog actueel? |

Introduceer identificeerbare observaties en bewijsverwijzingen, aanvankelijk naast
de bestaande `UNDERSTANDS`-velden. Een model stelt wijzigingen voor op basis van
concrete berichten; resolved/superseded verwijzen naar ondersteunend bewijs.
Een historische `learned`-status migreert als zelfbeoordeling, nooit als verzonnen
toetsbewijs. Oude strings behouden hun herkomst als legacy-observatie.

De mentor gebruikt korte, vrijwillige begripchecks in de normale conversatie:
in eigen woorden uitleggen, een uitkomst voorspellen of een nieuw voorbeeld
toepassen. Geen standaard examen en geen schijnprecies beheersingspercentage.
Vervang de voortgangsring door besproken aspecten, aangetoond begrip en open vragen.

Maak consolidatie atomair en bestand tegen gelijktijdige requests en retries;
versies/checkpoints voorkomen dubbele quiztellingen. Rebuild reconstrueert
afgeleide observaties, met behoud van correcties en bewijs. Toon een mislukking
en een herhaaloptie in plaats van succes te suggereren.

Acceptatie: opgelost probleem staat niet meer in actieve prompt; geschiedenis
blijft inspecteerbaar; rebuild en herhaling tellen bewijs niet dubbel; een nieuw
probleem kan later opnieuw actief worden; correcties blijven behouden.

## Fase 3 — Richting, hervatten en persoonlijke voorbeelden

- Een leerdoel of startvraag, bijvoorbeeld “deze paper begrijpen”, verbindt een
  bron, meerdere concepten en gesprekken. De mentor motiveert aanbevolen stappen.
- Een rustige hervatkaart naast de graph: doorgaan met een gesprek, een bewaarde
  vraag bekijken of een relevante verbinding verkennen. Geen ongevraagde takenlijst.
- Bewaar concrete voorbeelden/analogieën die aantoonbaar hielpen met hun herkomst.
  De lerende kan ze corrigeren of verwijderen.
- Maak herhalen optioneel, gebaseerd op bewijs en recentheid. Oud bewijs wordt
  als oud getoond, niet automatisch als vergeten geïnterpreteerd.
- Bronvragen gebruiken bewaarde citaten/context, met onderscheid tussen wat de
  bron zegt en de algemene uitleg van de mentor. Volledige bronopslag en actualiteit
  zijn afzonderlijke keuzes; de huidige installatie bewaart vooral bronmetadata
  en geselecteerde fragmenten.

## Fase 4 — Een onderhoudbare kaart met echte inhoud

Voeg hernoemen, duplicaten samenvoegen, relaties corrigeren en suggesties verwijderen
toe. Toon vooraf welke relaties, bronverwijzingen en gesprekslinks een samenvoeging
raakt. Gebruik een atomaire bewerking en herstelmogelijkheid; bewaar stabiele IDs.
Maak graphqueries consistent bij het huidige maximum van 500 nodes en bied later
gerichte buurten/filters voor grotere kaarten.

De bestaande inhoud is de initiële dataset. Bouw hierop voort met nieuwe bronnen.
Maak vóór onderhoud een herstelbare backup en toon de gevolgen van gerichte
wijzigingen. Verwijder niets op basis van een geraden “test”-label. Beoordeel de
volledige leerervaring met een nieuwe bron vóór bulkimport.

## Fase 5 — Instelbare mentor en aparte kinderinstallatie

Een mentorbrief bevat doel, toon, interesses, didactische voorkeuren en optioneel
een geavanceerde systeeminstructie. De brief geldt voor uitleg én chat. Voor een
kinderinstallatie komen ouderinstellingen achter oudertoegang en is zichtbaar
voor het kind welke grenzen en meldregels gelden.

Ontwerp contentgrenzen en ondersteuningssignalen apart. Gevoelige nieuwsgierigheid
is niet automatisch een noodsituatie; gebruik context en leeftijdspassende reacties.
Een eventuele melding deelt zo weinig mogelijk en belooft geen vertrouwelijkheid
die niet bestaat. Een vrije prompt alleen is onvoldoende voor deze functies.

Vóór implementatie van meldingen zijn concrete keuzes nodig: leeftijd, grenzen,
ontvanger/kanaal, triggers, gedeelde inhoud, retentie en gedrag bij twijfel/storing.
Bouw eerst configuratie, previews en gesimuleerde meldingen. Activeren van een
extern kanaal en versturen van echte berichten vereist expliciete toestemming;
dat is niet onderdeel van deze eerste implementatie.

## Uitvoering en controle

Werk per werkende stap. Gebruik geïsoleerde tests voor model-/databasegrenzen en
controleer frontend-build en de volledige flow met testfixtures. Gebruik bestaande
data niet als wegwerptest en voer tijdens verificatie geen geheugenrebuild uit.
Controleer UI op lege toestand, laden, fouten, herladen, terugnavigatie, beide talen
en keyboardbediening. Noteer welke checks daadwerkelijk zijn uitgevoerd en welke
een live omgeving/model nodig hebben.

## Voortgang

- [x] Bestaande plan en implementatie onderzocht; richting met Paul afgestemd.
- [x] Gefaseerd implementatieplan vastgelegd; v2 blijft historische basis.
- [x] Fase 1A: gedeelde context en retrybare consolidatie geïmplementeerd.
- [x] Fase 1B: persistente gespreksvoorstellen met expliciete acceptatie geïmplementeerd.
- [x] Fase 1C: zijpaden en terugnavigatie geïmplementeerd.
- [x] Fase 1: geïsoleerde tests, frontend-build en browsercontrole met fixtures.
- [x] UI/UX-tussenstap: Learn/Explore, illustraties, topicgroepen, zoomdetail en profielvoorkeur voor beweging.
- [ ] Fase 1: praktijkcontrole met draaiende Neo4j en echte modelantwoorden.
- [x] Fase 2: bewijs, zelfinschatting, geheugenhistorie en atomaire checkpoints.
- [x] Fase 2: unitchecks, echte Neo4j-transactietests, browserflow, build en synthetische modelcheck.
- [x] Fase 3: leerdoelen, hervatten, helpende voorbeelden, optionele terugblik en broncontext.
- [x] Fase 3: unitchecks, Neo4j-integratie, browserflows, build en synthetische modelcheck.
- [ ] Fases 4–5: gepland; kaartonderhoud is de volgende ontwikkelstap.

### Uitgevoerd op 10 september 2026

- 17 backendtests geslaagd zonder database/modelcalls: context, bronfragmenten,
  canonieke identiteit, consolidatie-retry, voorstelvalidatie, acceptatie,
  relatie-richting, afwijzen en herhaald accepteren.
- 4 frontendtests geslaagd: vertakken, terugkeren, cycli en corrupte/opgeslagen paden.
- Next.js productiebuild geslaagd.
- Browserflow met volledig onderschepte backend: voorstellen veranderen de kaart
  niet, afwijzen, bewaren, fout en opnieuw proberen, verkennen/heropenen,
  terugkeren naar de oorspronkelijke berichten, herladen, volledig scherm,
  toetsenbord en NL/EN. Geen browserfouten; screenshots visueel beoordeeld.
- Bestaande Engelse taalkeuze start nu zonder afwijking tussen serverrender en
  browserrender. Afhankelijkheden vastgelegd in `frontend/package-lock.json`.

### Grenzen van deze eerste stap

Docker draaide niet tijdens uitvoering. De nieuwe Cypher en modelkwaliteit zijn
daarom nog niet tegen een draaiende Neo4j/LLM geverifieerd. De browsercontrole
controleert UI-integratie met gesimuleerde antwoorden, geen echte opslag.
De bestaande database en testdata zijn niet aangepast.

Voorstelgeneratie is voorlopig een extra extract-modelcall na ieder chatantwoord,
met timeout van 15 seconden. Een storing hierin houdt het antwoord intact, maar
de kaarten kunnen dan ontbreken. Accepteren gebruikt naam/alias-resolutie; nieuwe
voorstellen krijgen pas bij `/learn` een embedding. Semantische deduplicatie bij
acceptatie en minder wachttijd zijn mogelijke verfijningen na praktijkfeedback.
Eerder voorgestelde namen uit de laatste 100 voorstellen voor een concept worden
onderdrukt; dit is geen algemene semantische blokkadelijst.

De UI toont voorstellen los van de berichten, ook uit beëindigde gesprekken.
Het leerpad herstelt actieve gesprekken; na consolidatie gebruikt de bestaande
chatroute de samenvatting in plaats van oude berichten te tonen. Een aparte
historieweergave hoort bij fase 3. De route bewaart conceptnamen per browsertab;
stabiele navigatie-IDs worden relevant bij hernoemen in fase 4.

Toevoegen via natuurlijke taal levert voorlopig een actiekaart die je aanklikt.
Automatisch uitvoeren van een expliciet chatverzoek is een latere uitbreiding.
`person_id`-controles zijn geen authenticatie; deze lokale éénpersoonsinstallatie
is daarmee niet geschikt voor blootstelling aan onbevoegde gebruikers. Ouderregels
en echte meldingen zijn nog niet gebouwd of geactiveerd.

Consolidatie na een modelstoring blijft nu retrybaar. Transactionele consolidatie,
concurrentiebeveiliging, veilig rebuilden bij gedeeltelijke uitval en duidelijkere
UI-feedback bij consolidatiefouten volgen in fase 2. De UI/UX-tussenstap heeft de permanente voortgangsring verwijderd. Besproken
aspecten blijven in het geheugen zichtbaar; bewijs van beheersing volgt in fase 2.


### Uitgevoerd op 12 september 2026 — UI/UX vóór fase 2

De goedgekeurde herinrichting is lokaal geïmplementeerd binnen de bestaande
architectuur. Learn krijgt een rustige gespreksweergave met optionele context,
Explore een gegroepeerde kaart met selectiepreview en behoud van kaartpositie.
Onderwijsillustraties ondersteunen flows, vergelijkingen, 2D-vectoren en balken;
ze blijven beschikbaar voor vervolgvragen en geheugenverwerking.

Zoomniveaus hebben korte uitleg. Leerroutes volgen uitsluitend opgeslagen
voorkennisrelaties, inclusief parallelle takken en detectie van cycli. Beweging
is een profielvoorkeur en respecteert verminderde beweging van het systeem.

Validatie: 22 backendtests, 9 frontendtests, productiebuild en gesimuleerde
browserflow geslaagd. Browsercontrole omvat ook NL/EN, mobiel, lege kaart,
illustraties, terugnavigatie, zoomdetail, bewegingsvoorkeur en fout/herstel.
De database/testdata zijn niet aangepast. Echte modelkwaliteit, opslag na
backendherstart en groepering met echte bronnen blijven praktijkchecks.

Zie [implementatieverslag en screenshots](design/implemented-2026-09-12/README.md)
voor de precieze scope en volgende stappen. Fase 2 is nog niet uitgevoerd.


### Correctie na gebruikerstest — 12 september 2026

De statische topicblokken zijn vervangen door een bewegende kennisgraph met
zachte clustercontouren en lichte aantrekkingskracht naar de cursor. De hele
graph blijft zichtbaar; inzoomen onthult geleidelijk meer namen. Groepering volgt
werkelijke verbindingen in plaats van versnipperde domeinlabels. De profielkeuze
voor beweging en verminderde beweging blijven werken.

De controle gebruikt nu ook een alleen-lezen snapshot van de echte graph
(93 knopen, 68 relaties), naast de gesimuleerde leerflow. Zie
[correctieverslag](design/graph-restored-2026-09-12/README.md).

### Leerstart verduidelijkt — 12 september 2026

Een geselecteerd cluster heeft nu een startkaart met aanbevolen instapconcept
op basis van opgeslagen voorkennis en huidige zelfinschatting. De CTA begint
de uitleg; losse knopen openen direct Learn. Een leeg gesprek toont een grote
introductiekaart met de knop Start de les. Validatie: 12 frontendtests,
productiebuild en browserflow met onderschepte API-antwoorden geslaagd.
Zie [leerstart en screenshots](design/learning-entry-2026-09-12/README.md).

### Fase 2 uitgevoerd — 12 september 2026

Besproken inhoud, zelfinschatting en aangetoond begrip zijn gescheiden. Bewijs
verwijst naar concrete leerlingcitaten, bericht, gesprek en datum. Moeilijkheden
kunnen worden opgelost, gecorrigeerd en opnieuw geactiveerd; de historie blijft
zichtbaar. Leerlingcorrecties zijn herkenbaar en worden geen modelbewijs.

Consolidatie schrijft geheugen, profiel en gesprekscheckpoint atomair. Fouten
laten berichten intact en bieden een retry. Herhalen, gelijktijdige verzoeken
en opnieuw opbouwen tellen bewijs niet dubbel. Opnieuw opbouwen herhaalt
geaccepteerde checkpoints; oude gesprekken worden niet opnieuw door een model
beoordeeld. Historische aggregaten blijven als legacy herkenbaar.

De initiële dataset is behouden. Vóór migratie is een lokale backup gemaakt;
alle 186 oorspronkelijke records zijn teruggevonden en de inhoud van concepten,
bronnen, conceptbronnen in voorbereiding en berichten is ongewijzigd. De migratie
is additief: oude begrepen-vlaggen worden zelfinschattingen zonder verzonnen datum
of bewijs. 16 bestaande geheugentoestanden hebben het nieuwe formaat.

Validatie: 29 backendtests, echte Neo4j-controles met geïsoleerde en opgeruimde
fixtures, mentor- en geheugenbrowserflows en frontend-productiebuild geslaagd.
Een synthetisch rekenvoorbeeld is ook met het ingestelde model gecontroleerd.
Dit vervangt geen praktijkbeoordeling van didactische kwaliteit.
Zie [fase 2: gebruik, validatie en beperkingen](design/phase2-2026-09-12/README.md).

### Fase 3 en navigatieverfijning — 13 september 2026

- De onderwerpdropdown is verwijderd. Clusters selecteer je op de graph; een
  chip maakt de focus zichtbaar en kan hem wissen. Lijstweergave is een optioneel,
  toegankelijk alternatief voor dezelfde nodes en volgt de bestaande zoekterm.
- “Geen verbindingen” betekent geen opgeslagen relaties. De nieuwe knop **Stel
  verbindingen voor** vraagt om relevante voorkennis/verwanten met motivatie en
  een beginpunt. Bestaande voorstelkaarten laten de lerende kiezen wat wordt
  verkend of bewaard. Start de les blijft de eigenlijke les starten.
- **Mijn leerrichting** bewaart doelen/vragen met één of meer concepten en een
  optionele bron. Routes volgen uitsluitend bestaande voorkennisrelaties; cycli
  worden gemeld. De mentor krijgt het actieve doel als context, ook bij zijpaden.
  Gesprekken worden aan het doel gekoppeld. Er is één actief doel; doelen kunnen
  worden gepauzeerd, hervat en afgerond. Stapafvinkingen zijn navigatiekeuzes,
  geen beheersingsbewijs.
- Een rustige hervatregel brengt je naar de volgende stap of het laatste gesprek.
  Afgesloten gesprekken worden vanuit hun geheugen voortgezet.
- **Dit hielp mij — bewaar** bewaart een mentorbericht als door de lerende bevestigd
  helpend voorbeeld. Aanpassen/verwijderen verandert het oorspronkelijke bericht
  niet. Alleen de actuele bewaarde tekst wordt bij relevante gesprekken hergebruikt.
- Optionele terugblik gebruikt het meest recente positieve bewijs per concept.
  Na veertien dagen kan een voorstel met datum en citaat verschijnen; ouderdom
  wordt niet vertaald naar vergeten of lagere beheersing.
- Bronvragen krijgen opgeslagen citaten, tijdcodes en samenvattende context,
  afzonderlijk van algemene uitleg. De mentor claimt geen volledige bronlezing.

Validatie: 35 backendtests, 12 frontendtests, productiebuild, echte Neo4j-controles
voor fases 2 en 3, plus browserflows voor mentor, graph en fase 3 geslaagd.
Een synthetische modelcheck onderscheidde een broncitaat van algemene uitleg
zonder claims over niet-beschikbare broninhoud. Alle 191 bestaande records en hun
properties waren na de geïsoleerde tests ongewijzigd; er bleven geen fixtures over.
De service is weer online; lokale backup: `backups/before-phase3-2026-09-13.json`.

Zie [fase 3: gebruik en grenzen](design/phase3-2026-09-13/README.md).

### Homepage verder vereenvoudigd — 14 september 2026

Alle zoeken en navigeren zitten nu in één uitklapbaar zoekveld: typen, een
onderwerp kiezen of een cluster selecteren. De losse Lijstweergave en hervatregel
zijn verwijderd. Een geselecteerd cluster kan in het zoekveld worden gewist.

De vaste rechterkolom **Jouw leerplek** combineert het geselecteerde onderwerp,
het laatste gesprek, actieve en bewaarde leerdoelen en een ingang naar een ander
onderwerp. Wanneer selectie en laatste gesprek hetzelfde onderwerp zijn, verschijnt
geen dubbele hervatkaart. De concept-leerroute en bronnen zijn inklapbaar. Op mobiel
staat dezelfde kolom als scrollbaar paneel onder de graph.

Pannen toont geen blauwe focusrand meer; toetsenbordnavigatie behoudt een
focusindicatie. Zoeken en Toevoegen sluiten bij klikken buiten de kaart;
uitgeklapte informatie sluit bij klikken elders of Escape. Invoer in de
Toevoegen-kaart blijft bij sluiten bewaard.

De productiebuild en browserflows voor homepage en fase 3 zijn gecontroleerd;
zie [verslag en screenshots](design/home-navigation-2026-09-14/README.md).
Deze wijziging betreft de frontend; de bestaande leerdata blijven behouden.

### Profiel en Engels — 14 september 2026

Het profiel heeft nu drie tabs: Instellingen (taal en beweging), Leervoorkeuren
(selecteerbare eigen voorkeuren en apart gekleurde mentorobservaties) en Geheugen
(conceptgeheugen en rebuild). Lange pillen breken af binnen hun paneel.

Expliciete keuzes staan afzonderlijk in `teaching_preferences`, blijven bewaard
bij consolidatie/rebuild en hebben voorrang op oudere afgeleide observaties;
een actuele gespreksvraag blijft leidend. Eigen tekst kan als voorkeur worden
toegevoegd. De mentor blijft observaties uit gesprekken aanvullen zonder de
eigen keuzes te veranderen. Bestaande observaties blijven in hun oorspronkelijke
taal beschikbaar en kunnen worden verwijderd als ze niet meer passen.

Pauls voorkeurstaal is op Engels gezet, zonder Neo4j te wissen. De servervoorkeur
vervangt bij laden een verouderde lokale taalkeuze. Nieuwe uitleg/geheugenupdates
gebruiken de voorkeurstaal; historische gesprekken en citaten worden niet herschreven.
De chat kan nog steeds aansluiten bij de taal van een nieuw gebruikersbericht.

Validatie: 35 backendtests, gerichte Neo4j-test met tijdelijke leerling voor
voorkeurbehoud/consolidatie/rebuild, profiel-browserflow (incl. fout/retry,
eigen pillen, bestaande Nederlandse tekst, mobiele layout) en productiebuild.

#### 14 September: saved content display language
- Added batched, cached English/Dutch display translations for descriptions, memory,
  profile observations, helpful examples and mentor message text.
- Original records and exact evidence/source quotations are preserved; translations
  have an original-text toggle and a retry path. No database reset or memory replay.
- Build and 37 unit tests passed. Synthetic browser translation/retry coverage added.
- Live personal-data translation verification awaits user approval after automatic
  approval review blocked the model call. Illustration labels and original edit
  fields are not translated by this display layer.

#### 14 September: voice input
- Added microphone / stop / cancel to the Learn question composer, English/Dutch
  status and error messages, a two-minute limit and editable transcription.
- Uses existing Gemini configuration; optional `VOICE_MODEL` override. No audio is
  stored in Neo4j or on disk by the app; only a manually sent question joins chat.
- Verified production build, 39 unit tests, simulated browser microphone recording
  and real Gemini transcription of synthetic speech. Physical microphone testing
  remains with the learner; no personal microphone was accessed during checks.

#### 14 September: automatic direct-video fallback
- Captions first; on failure, direct Gemini Interactions API with agentic processing.
- No full transcript generation. Concepts and relationships go to existing review.
- AI paraphrase provenance persists in source context; empty quote fields, approximate
  timestamp labels, explicit review notice. Mentor source quoting excludes AI moments.
- Live video AxzcWOxzkiw yielded 24 concepts, 64,880 total tokens. No concepts accepted
  by the test. Build, 46 backend tests and browser review check passed.
- Public-video preview availability still depends on Google; paste remains final
  fallback. Repeated imports repeat analysis; request times out after 240 seconds.
