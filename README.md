# Trellis: persoonlijke kennisgraph met AI-mentor

De actuele vervolgrichting, acceptatiecriteria en implementatiestatus staan in
[Implementation-plan-v3.md](Implementation-plan-v3.md). Trellis is een mogelijke
nieuwe naam; de installatie heet voorlopig Trellis. De eerste vervolgstap maakt
uitleg persoonlijker en voegt conceptvoorstellen en terugnavigatie aan gesprekken toe.

## Profiel en taal

Het profiel opent met **Settings** voor taal en beweging. **Teaching preferences**
bevat blauwe eigen keuzes en paarse mentorobservaties; **Memory** bevat het
conceptgeheugen en de rebuildoptie. Engelse uitleg kan voortbouwen op bestaande
Nederlandse herinneringen: een taalwissel vereist geen database-reset.

## Homepage: één zoekveld en één leerplek

Klik op het zoekveld voor zoeken, onderwerpen en clusters. Rechts staat
**Jouw leerplek** met je selectie, laatste gesprek en leerdoelen. De losse
hervatregel en Lijstweergave zijn hierin opgenomen. Menu’s sluiten bij buiten
klikken; de graph krijgt geen blauwe rand bij pannen.
Zie [de actuele homepage](design/home-navigation-2026-09-14/README.md).

## Nieuw: fase 3 — leerrichting en hervatten

**Jouw leerplek** bewaart een leerdoel met onderwerpen en een optionele bron,
met een route op basis van bestaande voorkennis. Hervat een gesprek, bewaar
voorbeelden die hielpen en kies desgewenst een korte terugblik. De contextkolom
biedt nu **Stel verbindingen voor** en **Bespreek deze bron**. De onderwerpdropdown
is vervangen door selectie op de graph; Lijstweergave blijft optioneel.

Zie [fase 3: gebruik, validatie en screenshots](design/phase3-2026-09-13/README.md).
Fases 1–3 en de UI-verfijningen zijn geïmplementeerd. Fases 4–5 blijven gepland.

## Nieuw: rustige Learn / Explore-werkruimte

De UI/UX-herinrichting is geïmplementeerd: gegroepeerde kaart, zoomdetail met
uitleg, voorkennisroutes, rustige mentorweergave en onderwijsillustraties.
Beweging is instelbaar in Mijn profiel. Zie het
[implementatieverslag met screenshots](design/implemented-2026-09-12/README.md)
voor de oorspronkelijke herinrichting; zie ook de
[herstelde levende graph](design/graph-restored-2026-09-12/README.md) en
[duidelijke leerstart](design/learning-entry-2026-09-12/README.md).

## Nieuw: fase 2 — begrip en veranderend geheugen

De bestaande inhoud is de initiële dataset en blijft behouden. Geheugen scheidt
besproken onderwerpen, je eigen inschatting en bewijs uit concrete leerlingberichten.
Moeilijkheden hebben een inspecteerbare historie en kunnen worden gecorrigeerd,
opgelost of opnieuw geactiveerd. Opslaan en opnieuw opbouwen gebruiken atomaire
checkpoints; een mislukte update kan veilig opnieuw worden geprobeerd.

Probeer het op [localhost:3000](http://localhost:3000): voer een gesprek, beëindig
het en open **Bekijk geheugen**. Zie het
[fase 2-verslag](design/phase2-2026-09-12/README.md) voor gebruik en validatie.

## Nieuw: doorlopende gesprekken

- **Persoonlijke uitleg:** “Leg uit” gebruikt je leerprofiel, bestaande
  begripstoestand, broncontext en de laatste twaalf berichten uit het actieve gesprek.
- **Verder verkennen:** onder een chatantwoord kunnen conceptkaarten verschijnen.
  Verkennen opent het concept; Bewaar voor later voegt het toe aan de kaart;
  Afwijzen voegt niets toe. De mentor kan zulke kaarten ook maken als je zelf
  om een onderwerp vraagt. De klik bevestigt de toevoeging.
- **Je leerpad:** vanuit een conceptkaart of de mini-boom kun je een zijpad openen
  en terugkeren naar een eerder concept. Het pad blijft bij herladen in dezelfde
  browsertab bewaard. Gesprekken blijven in Neo4j; geconsolideerde gesprekken
  worden via hun geheugen hervat.

Deze eerste fase is gecontroleerd met geïsoleerde tests en een gesimuleerde
browserflow. Praktijkcontrole met Neo4j en echte modelantwoorden staat nog open.

### Extra API

`POST /chat` en `GET /chat/{concept}` leveren ook `suggestions` met naam,
definitie, reden, relatietype/richting en status. Voorstellen staan als
`ConceptSuggestion` bij een `ChatSession`, los van de conceptkaart.

- `POST /suggestions/{id}/accept`: `{person_id, action: "explore" | "save"}`.
- `POST /suggestions/{id}/dismiss`: `{person_id}`.

Accepteren schrijft concept, relatie en acceptatiestatus in één transactie en
hergebruikt bekende namen/aliassen. Voorstellen hebben geen verzonnen bronlink.
Na een backendherstart voegt het bestaande schema-init de nieuwe unieke
`ConceptSuggestion.id`-constraint toe; er is geen data-reset nodig.

### Ontwikkelchecks

Vanuit de projectmap, met Python 3.10 of hoger:

```bash
python3 -m unittest discover -s backend/tests -v
cd frontend
node --test tests/learningTrail.test.mjs tests/atlas.test.mjs
npm ci
npm run build
```

`frontend/tests/mentor-flow.mjs` is een optionele Playwright-browsercheck tegen
een frontend op `http://127.0.0.1:3100` (instelbaar met `MENTOR_TEST_URL`). Alle
backendrequests worden onderschept; de check raakt geen persoonlijke data.
Installeer Playwright apart of wijs `MENTOR_PLAYWRIGHT_MODULE` naar die module;
`MENTOR_BROWSER_PATH` kan een bestaande Chromium-binary aanwijzen.

Concept-gedreven leren: je analyseert een bron, kiest zelf welke concepten je
wilt leren, en de graph groeit alleen met wat je daadwerkelijk oppakt.

## Starten
```bash
cp .env.example .env        # vul GEMINI_API_KEY in
docker compose up --build
```
- **Frontend: http://localhost:3000** — hier doe je alles
- Neo4j Browser: http://localhost:7474 (neo4j / changeme123)
- API docs: http://localhost:8000/docs

## Workflow
De hele flow is klikbaar vanuit de frontend; id's zie je nooit. De kaart is
het thuis: de knowledge graph vult het hele scherm, alles daarboven zweeft.

1. **Zoeken en toevoegen zijn gescheiden.** De balk bovenin is een zoekveld:
   typen filtert en highlight nodes in de graph; Enter op een onbekende term
   biedt "Leer dit" met niveau 1 t/m 5. "Toevoegen +" (⌘N) opent een
   invoerkaart met vier types: Onderwerp (term + context, "Leer" of
   "Genereer bron over dit onderwerp"), Transcript, YouTube (alleen url) en
   Paper/tekst (vast plakvak, titel, type, url). Esc sluit de kaart.
2. **Kandidaten review je in een paneel.** Na een analyse opent rechts het
   review-paneel: een boom van kandidaten (hoofdtopics met subtopics uit
   `candidate_relations`, losse onderwerpen apart), gesorteerd op importance,
   per item sterren, "in N van M delen", eerste tijdcode en uitklapbaar
   definitie + citaat. Hoofdtopic aanvinken vinkt de subtopics mee (met
   "indeterminate" bij deels). Kandidaten die al in je kaart staan zijn
   gemarkeerd en alleen te koppelen aan de bron. "Voeg toe aan mijn kaart"
   (`POST /candidates/commit`) schrijft ze als Concept met status `queued`
   ("Te leren", goud), koppelt de bron met citaten en tijdcodes en legt de
   relaties uit de analyse, ook naar bestaande nodes. Lange bronnen worden in delen gelezen; de balk toont
   "deel 4 van 9".
3. **Verken de graph.** Kleur is status: blauw = `learning`, goud = `queued`
   (opgenomen, nog niet geleerd), grijs gestippeld = `suggested` (door de
   mentor voorgesteld als voorkennis), groen = `learned`.
   De bewegende kaart groepeert verbonden knopen binnen zachte contouren.
   Hoofdonderwerpen hebben namen; inzoomen onthult geleidelijk meer namen,
   terwijl kleinere knopen zichtbaar blijven zonder labels. Korte tekst licht elk
   detailniveau toe; Fit brengt de selectie of kaart weer in beeld.
4. **Klik een node** voor een compacte preview en een volgorde op basis van
   opgeslagen voorkennisrelaties. **Verder leren** opent de mentor. Via Verkennen
   ga je terug naar dezelfde kaartpositie. De volgorde is geen bewezen curriculum.
5. **Praat met de mentor.** Eén gespreksvlak met vaste invoer, benoemd diepteniveau,
   optionele context en uitklapbaar geheugen, bronnen en notities. Geef een
   voorbeeld of vraag om een visualisatie. Ondersteunde illustraties worden bij
   het bericht opgeslagen en meegenomen bij vervolgvragen. Gespreksbeheer staat
   onder Gespreksopties. Eén suggestie staat direct in beeld; meer staan ingeklapt.
6. **Mijn profiel** staat rechtsboven: leerprofiel, taal en omgevingsbeweging.
   De knopen bewegen rustig en komen iets naar je cursor toe.
   De voorkeur wordt opgeslagen en respecteert verminderde beweging van je systeem.
   De mentor volgt de taal van je laatste bericht (of `ui_language` bij twijfel).
   Uitleg via `/learn` en geheugen gebruiken `ui_language`; conceptnamen blijven
   canoniek Engels. De legenda blijft onderaan de kaart beschikbaar.

Statussen lopen één kant op: `suggested` < `queued` < `learning` < `learned`;
een later `/learn` zet een `queued` concept op `learning`, een prerequisite-
suggestie verlaagt niets. Entity resolution zorgt dat bestaande concepten
hergebruikt worden in plaats van gedupliceerd.

## Hoe het geheugen werkt

Drie lagen, waarvan alleen de eerste echt waar is:

| Laag | Waar | Wat |
|---|---|---|
| 1 | `(:ChatSession)-[:HAS_MESSAGE]->(:ChatMessage)` | de ruwe gesprekslog. Bron van waarheid, deterministisch, wordt nooit door een model aangeraakt. |
| 2 | `(Person)-[:UNDERSTANDS]->(Concept)` | begripstoestand per concept: `covered`, `struggles`, `misconceptions`, `quiz_correct/wrong`, `summary`. |
| 3 | `Person.learning_profile` (JSON) | leerstijl over alle onderwerpen heen: `works_well`, `works_poorly`, `preferences`, `notes`. |

Laag 2 en 3 zijn afgeleid en volledig herbouwbaar: `POST /memory/rebuild/paul`
gooit ze weg en berekent ze opnieuw uit alle sessies in chronologische
volgorde. De **dream-fase** doet dat destilleren met één LLM-call per sessie,
getriggerd door "Beëindig" in de UI, of automatisch bij startup en elke tien
minuten voor sessies die langer dan 30 minuten stil liggen.

**Correcties blijven van jou.** Haal je iets weg uit je begripstoestand of
profiel, dan wordt dat een tombstone: consolidatie zet het niet terug, ook niet
na een rebuild, en ook niet in andere bewoordingen — de afgewezen observaties
gaan als instructie mee naar het consolidatiemodel. Handmatig aangepaste velden
krijgen `manual_fields` en worden alleen nog aangevuld, niet overschreven.

## API
| Endpoint | Doet |
|---|---|
| `POST /ingest/raw?title=&source_type=&url=&job_id=` | rauwe tekst (`text/plain`, geen JSON-escaping) → kandidaten |
| `POST /ingest/text` | zelfde, maar als JSON-body (`text, title, source_type, url, job_id`) |
| `POST /ingest/youtube` | `{url, job_id}`: transcript met tijdcodes + hoofdstukken uit de beschrijving → kandidaten |
| `GET /ingest/status/{job_id}` | voortgang van een lopende analyse: `{phase, done, total, message}` |
| `POST /ingest/topic` | laat het model zelf bronmateriaal schrijven → kandidaten |
| `POST /candidates/commit` | `{source_id, selected[], link_existing[], relations[]}` → kandidaten als `queued` Concept, bron gekoppeld, relaties gelegd (alleen entity resolution als LLM-call) |
| `POST /learn` | `{concept, context, level, person_id, source_id, mentions?, candidate_relations?}` → uitleg + schrijft naar de graph |
| `POST /concept/{name}/learned` | status → `learned`, maakt `UNDERSTANDS` |
| `GET /graph`, `GET /concept/{name}`, `GET /levels` | graph, detail (incl. mentions met tijdcode, url en type per bron), niveau-labels |
| `POST /ask` | losse vraag beantwoorden op niveau, gegrond in de graph |
| `POST /chat` | `{concept, message, person_id, level}` → mentor-antwoord + `session_id` |
| `GET /chat/{concept}` | actieve sessie met berichten en begripstoestand |
| `POST /chat/{concept}/new` \| `/end` | nieuwe sessie forceren \| afsluiten en consolideren |
| `GET /memory/{person}` | leerprofiel + alle begripstoestanden |
| `PATCH /memory/{person}/profile` \| `/concept/{name}` | handmatig corrigeren; `profile` accepteert ook `ui_language` (nl/en) |
| `POST /memory/rebuild/{person}` | laag 2 en 3 opnieuw afleiden uit laag 1 |

### Hoe een analyse werkt (`backend/app/pipeline.py`)
1. **Parsen** (`transcript.py`): tijdcodes blijven bewaard als `start_sec` per
   segment (YouTube "4:45", SRT-ranges, "[00:12]"); hoofdstuktitels worden
   markers. Voor YouTube komen de segmenten rechtstreeks uit de transcript-API
   en de hoofdstukken uit de videobeschrijving.
2. **Segmenteren op inhoud**: hoofdstukken zijn de grenzen (>12 min splitsen,
   <3 min samenvoegen). Zonder hoofdstukken wijst één goedkope
   `EXTRACT_MODEL`-call de onderwerpwisselingen aan (doel 8-15 minuten spraak
   per deel); mislukt die, dan vaste blokken. Kort materiaal is één deel.
3. **Parallel extraheren**: maximaal 6 delen tegelijk; elk deel krijgt de
   laatste ~10% van het vorige deel mee als "[voorafgaande context, niet
   extraheren]". Per kandidaat een letterlijk citaat plus het blok waar het
   staat, waaruit de tijdcode volgt. Een mislukt deel wordt één keer herhaald
   en daarna overgeslagen met een waarschuwing in `meta.warnings`.
4. **Samenvoegen**: kandidaten over delen heen gededupliceerd op naam/alias en
   op embedding (cosinus > 0,90; 0,80-0,90 laat het model bevestigen).
   Importance 1-5 = vooral in hoeveel delen het terugkomt (`chunk_count`),
   daarnaast de gemiddelde modelscore.
5. **Relaties**: één afsluitende call over de samengevoegde lijst levert
   `candidate_relations`; `/learn` neemt die over, maar alleen tussen
   kandidaten van dezelfde bron die daadwerkelijk geleerd zijn.

Response: `candidates[{name, definition, importance, chunk_count,
mentions[{start_sec, quote, chunk_idx}], context}]`, `candidate_relations`,
en `meta{chunks, skipped_chunks, duration_sec, chaptered, candidates_raw,
candidates_merged, tokens per fase, warnings}`. Bij `/learn` komen de
mentions als JSON op de `MENTIONED_IN`-relatie (plus `start_sec` van de
eerste), zodat de UI "Spring naar 47:12" kan tonen.

Ingest slaat niets op. De bron wordt geparkeerd als `:PendingSource` en
promoveert naar `:Source` bij de eerste `/learn` die er van leert.
PendingSources ouder dan 7 dagen worden bij startup opgeruimd; daarna geeft
`/learn` een nette melding dat je de bron opnieuw moet analyseren.

## Modellen
Twee taken, twee modellen, allebei via LiteLLM (`.env`):
- `EXTRACT_MODEL` — extractie en entity resolution. Volumewerk, dus flash.
- `MENTOR_MODEL` — uitleg in `/learn` en `/ask`. Vraagt redeneerkracht, dus pro.

`EMBED_MODEL`/`EMBED_DIM` liggen vast zodra de graph gevuld is: embedding-
ruimtes zijn onderling incompatibel.

## Handige Cypher (Neo4j Browser)
```cypher
// Wat ben ik aan het leren, en wat mis ik daarvoor?
MATCH (c:Concept {status:'learning'})<-[:PREREQUISITE_OF]-(p:Concept)
WHERE p.status <> 'learned' RETURN c.name, collect(p.name) AS mist;
// Hele graph
MATCH (c:Concept)-[r]-(o) RETURN c,r,o LIMIT 200;
// PageRank (GDS)
CALL gds.graph.project('g','Concept',{RELATED_TO:{orientation:'UNDIRECTED'},PREREQUISITE_OF:{},PART_OF:{}});
CALL gds.pageRank.stream('g') YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score ORDER BY score DESC LIMIT 20;
```

## Structuur
- `db/schema.cypher`: constraints, fulltext- en vector-index, datamodel
- `backend/app/llm.py`: LLM-abstractie (LiteLLM), modellen via .env
- `backend/app/transcript.py`: transcripten parsen naar segmenten met tijdcode
- `backend/app/pipeline.py`: gechunkte, parallelle extractie, merge, relaties
- `backend/app/extract.py`: normalisatie-wrapper, bron-registratie, entity
  resolution tegen de graph (embedding > 0.95 = zelfde; 0.80-0.95 = LLM beslist)
- `backend/app/learn.py`: concept + prerequisites naar de graph schrijven
- `backend/app/chat.py`: systeemprompt uit graph + laag 2 + laag 3, gespreksbeurten
- `backend/app/memory.py`: consolidatie, rebuild, handmatige correcties
- `backend/app/mentor.py`: niveau 1 (10-jarige) t/m 5 (ervaren engineer)
- `backend/app/graph.py`: alle Cypher
- `frontend/`: Next.js (App Router), graph via react-force-graph-2d; de
  UI-tokens (kleuren, fonts, glow) staan in `app/globals.css`, het ontwerp
  in `design/trellis.html`

## Volgende stappen
1. Kennisgatdetectie: leerpad voorstellen op basis van `UNDERSTANDS` en de
   `struggles` uit laag 2
2. Meerdere personen (Paul, zoon) met eigen niveau, geheugen en voortgang
3. De mentor zelf relaties in de graph laten voorstellen (nu bewust nog niet)
4. Zelfde compose-file op VPS + Tailscale

### Saved content language (14 September 2026)
The selected language now also controls display translations of concept descriptions,
memory summaries and observations, recorded teaching preferences, saved examples,
and mentor message text. Translations are generated by the configured extraction LLM
and cached in separate `ContentTranslation` nodes, keyed by source text and language.
The original graph, conversations, corrections and evidence remain unchanged.
“Translated · Original” switches back to the saved text; failed translations retain
that text and offer Retry. First-time translations appear after a short delay.
Original learner messages, evidence quotations, source quotations and edit fields
remain original; concept names remain stable navigation identities. Illustration
labels are not currently translated. New mentor responses use the existing language rules.

Validation: production build, 37 backend unit tests, and synthetic browser coverage
for translated memory, original toggling and failed-translation retry. Live translation
of personal content awaits explicit approval for sending it to the configured LLM.

### Voice questions (14 September 2026)
In Learn, click the microphone beside the question field, allow microphone access,
speak, then click Stop. The transcript is appended to the editable draft and is
never sent to the mentor automatically. Cancel discards the recording. Recordings
stop at two minutes; browser tracks are released on stop, cancel or navigation.
Audio is converted to mono WAV and sent via the backend to the existing Gemini
extraction model (`VOICE_MODEL` can override it). No OpenAI key is needed. Audio is
processed in memory and not saved by Trellis. Transcription uses the configured
provider's token pricing, not the OpenAI per-minute example discussed earlier.
Microphone access requires localhost or HTTPS. Chrome was verified with a simulated
microphone; other browsers depend on MediaRecorder and Web Audio support.

Validation: 39 backend unit tests, production build, browser recording/WAV conversion,
editable transcript append without auto-send, cancel and mobile layout. A generated
spoken question was transcribed through the actual Gemini connection correctly.

### YouTube retrieval failures (14 September 2026)
YouTube can reject automated caption requests (`RequestBlocked` / `IpBlocked`),
including from a previously working connection. Trellis now shows a concise,
localized recovery message and retains the failed URL. In Add → YouTube,
**Paste transcript instead** switches to manual transcript import while retaining
YouTube as source type and the original URL. Copy Show transcript from YouTube if
available; timestamped transcripts keep their time links. This does not remove
YouTube's upstream block or synthesize missing source text.

### Direct YouTube fallback
Caption retrieval remains first. If it fails, Trellis sends the canonical public
YouTube URL directly to Google's Interactions API using agentic video processing.
It extracts up to 30 concepts and relationships without generating a full transcript.
`VIDEO_MODEL` defaults to `EXTRACT_MODEL` (Gemini 3.7 Flash); the model must support
agentic video input. Existing Gemini credentials are used. The request has a
240-second timeout and does not retry model calls automatically.

Results enter the normal review flow as a pending source. Review displays an AI
video-analysis notice; saved context remains labelled as a paraphrase and timestamp
links as approximate. No generated text is saved in quote fields or passed to the
mentor as verified quotations. If video access also fails, manual paste remains.
Usage metadata retains Google's full usage breakdown, including processing/thought
usage; total tokens can exceed input plus output counts. No dollar estimate is
inferred from those counts. Repeat imports currently repeat analysis.

Validated on AxzcWOxzkiw: agentic direct analysis returned 24 concepts and 64,880 total
tokens. The earlier static diagnostic used 892,003 tokens with a different prompt;
this is not a controlled cost comparison. Tests: 46 backend tests, production build,
and browser review provenance check. Live test only analyzed; it did not accept or
add concepts to the learner's graph.

### Whole-graph learning roadmap (16 September 2026)
Explore defaults to the graph. The Graph / Learning path switch shares the search
row. Learning path organizes every saved concept into four visual stages: shared
foundations, core mechanisms, capabilities/applications, and specialist frontiers.
Expandable thematic modules show topics and understood counts. Topic buttons open
the mentor; arrow buttons return to the graph. Per-topic prerequisite routes remain
in the learning sidebar.

The read-only `/curriculum` endpoint asks the configured extraction model to propose
an overall teaching order from concept names, definitions, domains and relationships.
It does not send conversations or learner memories. Results are cached in process
by graph snapshot and language; changed content generates a fresh proposal. Missing
IDs are retained in a Needs placement module, invented IDs are discarded, and saved
prerequisites that conflict with stage placement are disclosed. A topic without
incoming edges is not automatically classified as foundational. The suggested start
is the first unmastered topic whose recorded prerequisites are marked understood.
Stage placement remains an AI proposal, not a verified assessment of difficulty.
Browsing never changes graph concepts, relationships or learner progress.

Validation: production build, curriculum coverage/conflict unit test and isolated
browser checks for complete coverage, start action, mentor entry and switch alignment.

### Visual roadmap navigation (16 September 2026)
The curriculum now uses compact expandable groups on a two-dimensional canvas.
Desktop learning depth runs left to right; additional groups extend vertically.
Ordinary scrolling and trackpad gestures retain native movement; dragging empty
canvas pans, while control-wheel/pinch and +/- zoom. Overview collapses groups and
fits the map (bounded zoom); My next step focuses and opens the recommended group.
Stage headings and controls stay outside the scrolling canvas. A position minimap
appears when navigating away from the default view. Narrow views place stages from
top to bottom. Expanded groups keep their topic list locally scrollable so a large
group does not push every other branch off-screen.

Only saved prerequisite relationships generate connecting arrows between groups.
The proposed stage order does not invent new prerequisite edges. This preserves
existing data and keeps topic-specific mentor routes unchanged. UI verification
covers expansion, zoom, overview, mobile width/height, and mentor entry.

### Branching layout correction (16 September 2026)
Replaced the fitted stage matrix with a minimum 1,940px-wide branching canvas.
Compact fixed-size modules have 200px horizontal breathing room; tree placement
centres each parent on its children. One strongest forward prerequisite parent is
shown per group. Where no forward prerequisite exists, a dashed stage-progression
link provides a proposed navigation route, explicitly distinguished from recorded
prerequisites and never saved to Neo4j. Extra prerequisite links remain in the graph
and mentor context. Group details open in an overlay without moving the route.
Checks include actual horizontal drag, overflow, group detail controls, mobile
layout, build, and a dense 16-group no-overlap/forward-edge layout check.
