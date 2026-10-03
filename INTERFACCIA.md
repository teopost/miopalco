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
- Dopo un'azione arriva un `toast` breve: «Segnalazione eliminata»,
  «Compito aggiunto».

## Stati e pastiglie

- Il palco e l'opportunità hanno due vocabolari diversi: `VENUE_STATUSES`
  (Lead, Prospect, Interessato, Cliente, Inattivo, Archiviato) e
  `GIG_STATUSES`. I colori vengono sempre da lì, mai scritti a mano.
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
