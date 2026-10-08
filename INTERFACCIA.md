# Standard dell'interfaccia di MioPalco

Le regole che l'app segue dappertutto, con il perché. Prima di toccare
l'interfaccia si legge questo file. Quando nasce una regola nuova, o una
vecchia cambia, si aggiorna qui nello stesso commit.

Tutta l'app è `static/index.html`: un foglio di stile, il markup delle
schermate e lo script in un file solo.

## Conferme

**Eliminare si conferma sempre con il foglio che sale dal basso.**
Si usa `confirmDestructive(domanda, onConfirm)`: un foglio con la domanda in
cima, **Conferma** in rosso e **Annulla**. Vale per ogni eliminazione (palco,
serata, compito, art director, band, utente, segnalazione…) e per le altre
azioni che non si possono disfare, come «Uscire senza salvare le modifiche?»
o «Vuoi uscire da MioPalco?».
Un'eliminazione non usa mai il pannellino sotto la riga: Stefano l'ha
chiesto il 3 ottobre 2026, dopo che le eliminazioni dell'Admin (utenti, band,
segnalazioni) erano nate col pannellino e non somigliavano al resto.

**Dove sta Elimina.** Nell'elenco, scorrendo la riga da destra a sinistra;
oppure nella scheda della cosa, come pulsante rosso «Elimina» nella barra
in alto subito prima di Salva (`nav-btn destructive`, per esempio nel
dettaglio di una segnalazione). Dopo l'eliminazione la scheda si chiude e
torna l'elenco.

**La domanda è scritta per intero.** I pulsanti dicono solo «Conferma» e
«Annulla», mai «Elimina serata». Quindi la domanda deve dire cosa succede e
cosa si perde: «Eliminare la band X? Se ne va con 12 palchi, serate…».

**Le azioni che hanno bisogno di dati aprono un pannellino sotto la riga.**
Confermare una serata, che vuole la data, o chiudere un compito, che fa
scegliere cosa viene dopo, non si applicano al tocco. Sotto la riga si apre
un `gig-panel esito` con la domanda (`esito-domanda`), i campi che servono
(gli stessi della scheda, non una variante) e in fondo a destra **Annulla** e
**Conferma**. Col pannellino aperto le altre righe non scorrono. La bozza si
rilegge prima di ogni ridisegno, così quello che hai scritto non sparisce.

## Schede e bozze

- Una scheda (palco, art director, band, segnalazione…) è una **bozza**: si
  salva solo con **Salva**, in alto a destra. **Indietro non salva**. Se c'è
  qualcosa di non salvato chiede «Uscire senza salvare le modifiche?»
  (`chiudiScartando`).
- Anche le scelte fatte da un foglio (stato, tipo, città…) restano in bozza
  fino a Salva. Si salvano subito solo le cose che non sono campi della
  scheda: preferito, foto, note, serate, compiti.
- **Nella scheda del palco Salva resta sulla scheda** (dal 5 ottobre 2026):
  salva, dice «Palco salvato» e ridisegna le righe, senza toccare la nota
  che stai scrivendo. Per uscire c'è Indietro, che a scheda pulita non chiede
  niente. Le altre schede per ora chiudono ancora salvando.
- **Nella scheda del palco Salva è grigio e non si tocca** finché non c'è
  niente da salvare, e si accende alla prima modifica, scritta o scelta da
  un foglio (dal 5 ottobre 2026, `aggiornaSalvaPalco` con la classe
  `spento`). Dopo il salvataggio torna grigio. Le altre schede per ora no.
- Il pulsante per tornare indietro porta il nome della schermata da cui si
  arriva («Admin», «Altro», «Segnalazioni»), non «Indietro», salvo nelle
  schermate di modifica.

## Righe che scorrono

- Le righe con azioni sono `.swipe-row`, fatte con lo scroll-snap (il
  movimento è quello nativo). Le azioni stanno in `.row-actions` (84px; con
  la classe `.two` sono 184px per due pulsanti).
- **Una riga senza azioni non ha `.row-actions`**, così non scorre e non
  promette niente: per esempio la propria riga fra gli utenti, una band con
  componenti, le righe col pannellino aperto.
- **Colori delle azioni**: rosso (predefinito) per quello che toglie o dice
  di no; grigio `.role` per quello che è benigno o reversibile; verde
  `.conferma` per un esito buono; marrone `.declina` per Declinato;
  `var(--tint)` (`.social-azione`) per quello che aggiunge senza togliere.
- **Un'azione che porta a uno stato ha il colore della pastiglia di quello
  stato**, preso dalla stessa tabella dei colori (per le segnalazioni
  `REPORT_STATI`): Fatto verde, Rifiutato rosso, Da valutare arancione. Il
  3 ottobre 2026 Fatto era grigio e Stefano ha notato che il pulsante e la
  pastiglia non si somigliavano.
- **Si scorre solo da destra a sinistra.** Lo scorrimento da sinistra a
  destra (Elimina sulle segnalazioni) è stato provato il 3 ottobre 2026 e
  tolto lo stesso giorno, perché a Stefano risultava scomodo. Un'azione che
  non sta fra quelle che compaiono scorrendo va nella scheda della cosa,
  nella barra in alto accanto a Salva.
- Il trascinamento col mouse scatta aperto o chiuso, mai a metà, e il
  rilascio non conta come clic.
- **Aprendo una scheda le sue righe scorse si richiudono**
  (`chiudiScorrimenti`, dopo averla resa visibile). Le righe disegnate da
  un elenco ripartono chiuse da sole; quelle fisse nell'HTML (i social con
  «Prendi la copertina» nel palco e nell'art director, la riga Posizione
  con «Ricerca avanzata» nel palco) no, e il 5 ottobre
  2026 si ritrovavano aperte rientrando, anche in un altro palco. Una
  scheda nuova con righe scorrevoli fisse va aggiunta allo stesso modo.

## Elenchi da cui si sceglie più di una cosa

- Quando una schermata intera serve a scegliere più righe (i palchi della
  zona proposti alla band nuova, dal 7 ottobre 2026), ogni riga si tocca
  per intero e ha in coda un cerchio che si riempie del colore `--tint`
  con la spunta (`.partenza-check`). Partono tutte scelte, in cima c'è
  «Togli tutti / Scegli tutti», l'intestazione dice «N DI M SCELTI» e il
  pulsante in fondo dice quante cose fa («Carica 8 palchi»), spento a zero.
  Nei fogli dal basso resta invece la spunta di `openSheet` con
  `multiSelect`.

## Nomi, classi, id

- **Prima di inventare una classe o un id, cercalo nel file** (`grep -n
  "\.nome" static/index.html`). Il foglio è uno solo: se il nome esiste già
  e la definizione vecchia sta più in basso, vince quella. Il 15 settembre
  2026 la barra dei mesi dell'Agenda è nata come `.month-bar`, nome già
  usato dalle barre cremisi della Home, ed è diventata tutta rossa.
- In caso di collisione usa un prefisso italiano del posto in cui vive
  (`mese-bar`, `utente-…`, `rep…`).
- Il codice parla inglese dove c'era già (`locations`, `gigs`), l'app parla
  italiano. Nell'interfaccia si dice **Palco/Palchi**, mai «palcoscenico».

## Testi e dati

- Quello che scrivono gli utenti (nomi di palchi, persone, note) passa da
  `dato()` o `setDato()`, che aggiungono `translate="no"`: un telefono in
  inglese traduce l'interfaccia, ma non «La buca ai confini del mondo».
- Sotto le schede, una `scope-note` dice in una riga cosa entra in
  quell'elenco e cosa no.
- I `section-footer` spiegano con parole semplici cosa fa una sezione,
  soprattutto quando la regola non si vede dalle righe.
- In un foglio di scelta, quando per scegliere bene serve più del nome,
  la voce ha una seconda riga in piccolo (opzione `sub` di `openSheet`,
  allineata a sinistra). Per esempio i profili Instagram trovati mostrano
  follower, post e la descrizione del profilo, come la mostrerebbe Google.
- Dopo un'azione arriva un `toast` breve: «Segnalazione eliminata»,
  «Compito aggiunto».

## Stati e pastiglie

- Il palco e l'opportunità hanno due vocabolari diversi: `VENUE_STATUSES`
  (Lead, Prospect, Interessato, Cliente, Inattivo, Archiviato) e
  `GIG_STATUSES`. I colori vengono sempre da lì, mai scritti a mano.
- **Sulla mappa non ci sono i palchi Inattivi** (dal 7 ottobre 2026,
  `sullaMappa`): restano nell'elenco, e sulla mappa tornano solo se nei
  Filtri è spuntato lo stato Inattivo, o quel segnalino solo se lo cerchi
  per nome nella ricerca della mappa.
- La pastiglia del palco ha il bordo (`.row-badge.contorno`), quella
  dell'opportunità è piena. Tutte e due stanno in coda alla riga, a destra.

## Grafici

- Niente librerie di grafici: barre in CSS e colori presi dai token del
  tema, così funzionano offline e seguono chiaro e scuro.
- Un anno ha lo stesso colore in tutta l'app: si chiede a
  `coloreAnno(anno)` (token `--anno-0..4`, `--anno-vecchio`) e, se gli anni
  stanno nello stesso disegno, si aggiunge `legendaAnniHtml()`. La tavolozza
  è passata dal validatore della skill `dataviz` (daltonismi, contrasto in
  chiaro e scuro): per cambiarla bisogna rifare quel passaggio, non
  sceglierla a occhio.

## Schermate e menu

- **Ogni elenco ha il titolo grande, e scorrendo diventa piccolo al centro
  della barra**, come i Palchi. Nei tab, la coppia `scroll…`/`nav…` sta
  nell'elenco passato a `collegaTitoloScorrevole`. Nelle schermate
  secondarie che sono elenchi basta l'attributo `data-titolo-grande` sulla
  `section`: il titolo grande lo crea lo script copiando quello piccolo
  (`.inline-title`) e lo tiene allineato se cambia. Le schede di modifica
  (un palco, un template, una segnalazione) non hanno il titolo grande. Il
  3 ottobre 2026 la Cassa non era collegata e nelle schermate secondarie il
  titolo piccolo non si vedeva mai: Stefano ha chiesto di renderle tutte
  come i Palchi.
- Le schermate secondarie sono `section.screen.pushed`: si aprono con
  `apriPushed(id)`, si chiudono con `chiudiPushed(id)` e si registrano in
  `addEdgeSwipeBack`, per tornare indietro con lo scorrimento dal bordo.
- **L'Indietro del telefono** (tasto o scorrimento dal bordo su Android)
  fa quello che fa il pulsante in alto a sinistra della schermata in cima:
  lo preme davvero (`indietroDelTelefono`), quindi valgono le sue regole,
  «Uscire senza salvare?» compreso. Un foglio aperto si chiude per primo;
  con niente da chiudere l'app si chiude. Funziona perché l'app tiene una
  voce in più nella cronologia (`armaIndietro`). Fino al 7 ottobre 2026
  Indietro su Android chiudeva l'app da qualunque schermata. Conseguenza:
  **una schermata secondaria deve avere il suo pulsante per tornare come
  primo `button.nav-btn` della `.navbar-row`**, altrimenti Indietro esce
  dall'app.
- **Menu Altro**: una voce nuova va in *Tabelle* se è una lista da cui si
  sceglie, in *Impostazioni* se vale per una persona o un dispositivo, in
  *Altro* se è un'anagrafica o si usa spesso. Le cose dell'amministratore
  vanno in *Admin*, che si vede solo con `me.is_admin`.
- I link che aprono l'app in un punto preciso (notifiche, scorciatoie
  dell'icona) sono `/?qualcosa=…`. Li legge una funzione `apri…DalLink`
  nella catena dopo `loadAllData`, che toglie il parametro dall'indirizzo.

## Prima di dire «fatto»

- Ogni modifica all'interfaccia si prova in un browser (Chromium headless,
  istanza di prova su una **copia** del database), con uno screenshot quando
  conta come appare.
- `static/` sta dentro l'immagine Docker: senza `docker compose up -d
  --build` sul telefono non cambia niente. Dopo ogni deploy si dicono build
  e impronta (`/api/version`).
