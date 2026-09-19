# Fase 2 — 12 september 2026

Geïmplementeerd in de bestaande lokale installatie: http://localhost:3000.
De initiële dataset blijft behouden en wordt verder uitgebouwd.

## Proberen

1. Open een onderwerp en voer een gesprek. De mentor kan een korte, vrijwillige
   begripsvraag aanbieden; deze mag worden overgeslagen.
2. Beëindig het gesprek om het geheugen bij te werken. Inactieve gesprekken worden
   ook door de bestaande achtergrondverwerking geconsolideerd.
3. Open **Bekijk geheugen**. Bekijk besproken inhoud, concrete citaten als bewijs,
   actieve moeilijkheden en de historie. Stel je leerintentie en eigen begrip in.
4. Markeer een moeilijkheid als opgelost of onjuist. De historie bewaart deze
   leerlingcorrectie; via opnieuw activeren kan het onderwerp terugkomen.
5. Bij een mislukte geheugenupdate blijven berichten bewaard en verschijnt een
   retryknop. Opnieuw opbouwen herhaalt opgeslagen checkpoints met behoud van
   bewijs en correcties.

## Gedrag en grenzen

- Besproken inhoud is geen bewijs van begrip. Zelfinschatting blijft apart.
- Bewijs vereist een exact citaat uit een leerlingbericht, met gesprek, volgnummer
  en datum. Een citaat maakt een modelbeoordeling controleerbaar, niet onfeilbaar.
- Opgeloste en vervangen observaties verdwijnen uit de actieve mentorcontext.
  Een verouderde samenvatting wordt apart bewaard tot er een nieuwe recap is.
- Oude begrip-vlaggen zijn zelfinschattingen met onbekende datum. Oude aggregaten
  blijven legacy; er wordt geen bewijs achteraf verzonnen.
- Rebuild is checkpoint-replay, geen nieuwe modelanalyse van oude gesprekken.
- De observatiehistorie geldt voor conceptgeheugen. Profielvoorkeuren behouden
  hun bestaande correctiemogelijkheden; deze hebben geen vergelijkbare historie-UI.
- De installatie blijft bedoeld voor één leerling. Langdurige didactische
  kwaliteit en groei naar grote datasets vragen verdere praktijkfeedback.

## Validatie

29 geïsoleerde backendtests en de frontend-productiebuild zijn geslaagd. Echte
Neo4j-transactietests controleren rollback, retry, dubbele en gelijktijdige
consolidatie, nieuwe berichten tijdens verwerking, correcties en herhaalde
rebuilds. Hiervoor zijn uitsluitend tijdelijke, unieke fixtures gemaakt en
verwijderd. Browserflows met onderschepte API-antwoorden controleren de mentor
en geheugenbediening inclusief fout en retry. Een synthetisch rekenvoorbeeld
met het ingestelde model leverde geldig bewijs uit het exacte leerlingcitaat.

Voor migratie is lokaal `backups/before-phase2-2026-09-12.json` opgeslagen.
Alle 186 oorspronkelijke records zijn behouden; de 160 concept-, bron-,
voorbereidingsbron- en berichtrecords hebben ongewijzigde eigenschappen.
16 geheugentoestanden zijn additief naar het nieuwe formaat gemigreerd.

De volgende geplande ontwikkelstap is fase 3; zie het
[actuele implementatieplan](../../Implementation-plan-v3.md).
