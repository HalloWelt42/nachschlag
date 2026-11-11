<script lang="ts">
  // Startseite, Variante A (Entwurf mockups/start-a.html): Suche in der Mitte, darunter Stöbern mit einem Zufallsfund
  // je Buch mit Lesedesign und die Bibliothek mit ihren Büchern und Fähigkeiten. Variante B (start-b.html, WIKI-7) wie
  // ein Magazin: groß der Artikel für heute aus den eigenen Themen, daneben Weiterlesen und Merkzettel, darunter das
  // Thema als Reihe; die Suche steht dann nur im Kopf. Welche, wählt das Gerät.
  import { onMount } from "svelte";
  import { geraet, seitenFehler, Seitenkopf } from "appkern-oberflaeche";
  import Suchfeld from "../teile/Suchfeld.svelte";
  import Kachel from "../teile/Kachel.svelte";
  import Sprachmarke from "../teile/Sprachmarke.svelte";
  import { archivAendern, bezeichnung, bibliothek, bibliothekLaden, buch as buchVon, datum, nutzbar, zahl } from "../lib/bibliothek.svelte";
  import { artikelHolen, heuteHolen, zufallHolen, type Heute } from "../lib/schnittstelle";
  import { STARTANSICHTEN, startansicht, startansichtMerken } from "../lib/ansicht.svelte";
  import { themaHolen } from "../lib/themen.svelte";
  import { Auswahl } from "appkern-oberflaeche";
  import Buchkachel from "../teile/Buchkachel.svelte";
  import Buendelebene from "../teile/Buendelebene.svelte";
  import { buendelHinweis, ordnen, reihenfolge } from "../lib/buendel";
  import type { Art, Buch } from "../lib/typen";
  import { lesen } from "../lib/ziele";
  import { gehe } from "appkern-oberflaeche";
  import { meins, meinsLaden, verlaufHolen, wann, type Verlaufseintrag } from "../lib/meins.svelte";
  import { lader } from "../lib/buecherlader.svelte";
  import Buchzeichen from "../teile/Buchzeichen.svelte";

  const WEITERLESEN = 4;                 // Karten im Entwurf
  const MERKZETTEL = 5;
  const FERTIG_AB = 0.95;                // so weit gelesen gilt als fertig, nicht mehr zum Weiterlesen
  let weiterlesen = $state.raw<Verlaufseintrag[]>([]);

  interface Fund { buch: Buch; pfad: string; titel: string; einleitung: string }


  let funde = $state<Record<string, Fund | null>>({});
  const REIHE = 6;                       // Artikel des Themas unter dem Artikel für heute
  const magazin = $derived(startansicht.wert === "b");
  let heute = $state.raw<Heute | null>(null);
  let heuteGeladen = $state(false);
  let themaReihe = $state.raw<{ titel: string; eintraege: { buch: string; pfad: string; titel: string; bild: string; anteil: number }[] } | null>(null);
  $effect(() => {
    if (!magazin) return;
    let aktuell = true;
    heuteHolen().then(async (h) => {
      if (!aktuell) return;
      heute = h;
      heuteGeladen = true;
      if (!h) return;
      const t = await themaHolen(h.thema_id);
      if (aktuell) themaReihe = { titel: t.titel, eintraege: t.eintraege.filter((e) => e.buch && e.pfad !== h.pfad).slice(0, REIHE) };
    }).catch(() => aktuell && (heuteGeladen = true));
    return () => { aktuell = false; };
  });
  let fehler = $state("");

  // Archiv der Quellen (WIKI-46): die Bibliothek zeigt die aktiven, das Archiv darunter; gezählt und gestöbert wird in
  // allem, was nutzbar ist (aktiv oder mitgenutzt)
  const aktive = $derived(bibliothek.buecher.filter((b) => !b.archiv));
  const archivierte = $derived(bibliothek.buecher.filter((b) => b.archiv));
  const artikelGesamt = $derived(bibliothek.buecher.filter(nutzbar).reduce((s, b) => s + b.artikel, 0));
  const mitLesedesign = $derived(bibliothek.buecher.filter((b) => b.faehigkeiten.lesedesign && nutzbar(b)));
  let archivFehler = $state("");
  async function archiv(kennung: string, aenderung: { zustand?: "archiv" | "aktiv" | null; mitnutzen?: boolean }) {
    try {
      archivFehler = "";
      await archivAendern(kennung, aenderung);
    } catch (f) {
      archivFehler = seitenFehler(f);
    }
  }

  async function zufallsfund(b: Buch) {
    try {
      const z = await zufallHolen(b.kennung);
      const a = await artikelHolen(b.kennung, z.pfad);
      const fund = { buch: b, pfad: a.pfad, titel: a.titel, einleitung: a.einleitung };
      funde = { ...funde, [b.kennung]: fund };     // erst nach dem Abwarten zusammensetzen
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  onMount(async () => {
    void meinsLaden(true);
    verlaufHolen(30, 0, "artikel").then((v) => (weiterlesen = v.filter((e) => e.buch && e.anteil < FERTIG_AB).slice(0, WEITERLESEN)))
      .catch(() => {});
    await bibliothekLaden();
    for (const b of mitLesedesign) void zufallsfund(b);
  });
</script>

<div class="inhalt-stufe" data-schrift="klein">
<div class="rollfeld" style="padding: 0">
  <div class="start-innen" class:magazin>
    <div class="start-wahl">
      <Auswahl wert={startansicht.wert} symbol="fa-table-cells-large" titel="Startseite, bleibt auf diesem Gerät eingestellt"
               optionen={STARTANSICHTEN} onwahl={startansichtMerken} />
    </div>
    {#if magazin}
      <section class="heute">
        {#if heute}
          <button class="heute-karte" onclick={() => heute && lesen(heute.buch, heute.pfad)}>
            {#if heute.bild}<img src={heute.bild} alt="" />{/if}
            <span class="heute-text">
              <span class="fund-etikett"><i class="fa-solid fa-sun"></i>Für heute</span>
              <span class="t">{heute.titel}</span>
              {#if heute.einleitung}<span class="auszug">{heute.einleitung}</span>{/if}
              <span class="grund"><i class="fa-solid fa-layer-group"></i>{heute.grund}</span>
            </span>
          </button>
        {:else if heuteGeladen}
          <p class="leer-hinweis">Der Artikel für heute kommt aus deinen Themen: lege auf der Seite Themen eines an und sammle Artikel darin.</p>
        {/if}
      </section>
    {:else}
      {#if !geraet.mobil}<h1 class="such-titel">Was möchtest du nachschlagen?</h1>{/if}   <!-- am Telefon zu viel Platz (WIKI-67) -->
      <!-- das große Suchfeld bleibt beim Rollen stehen, die Überschrift rollt weg (WIKI-70) -->
      <Seitenkopf rand="var(--start-rand)">
        {#snippet kopf()}
          <div class="suchmitte">
            <Suchfeld gross />
            {#if bibliothek.buecher.length}
              <div class="unter">Index über <span class="zahl">{zahl(artikelGesamt)}</span> Artikel in {bibliothek.buecher.filter(nutzbar).length}
                {bibliothek.buecher.filter(nutzbar).length === 1 ? "Quelle" : "Quellen"}</div>
            {/if}
          </div>
        {/snippet}
      </Seitenkopf>
    {/if}

    {#if weiterlesen.length}
      <section class="weiterlesen">
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-book-open-reader"></i>Weiterlesen</h2>
          <button class="alle" onclick={() => gehe("verlauf")}>Verlauf</button></div>
        {#if magazin}
          <div class="liste">
            {#each weiterlesen as e (e.id)}
              <div class="liste-zeile">
                <button class="liste-ziel" onclick={() => lesen(e.buch, e.pfad)}>
                  {#if e.bild}<img src={e.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-book-open"></i></span>{/if}
                  <span><span class="t">{e.titel}</span><span class="u">{e.abschnitt ? `bei ${e.abschnitt}` : "am Anfang"}</span></span>
                  <span class="rechts">{Math.round(e.anteil * 100)} %</span>
                </button>
              </div>
            {/each}
          </div>
        {:else}
        <div class="reihe">
          {#each weiterlesen as e (e.id)}
            <Kachel bild={e.bild} titel={e.titel} untertitel={e.abschnitt ? `bei ${e.abschnitt}` : ""} ziel={() => lesen(e.buch, e.pfad)}>
              {#snippet fuss()}
                <span class="lesestand-fuss"><span class="spur"><span style="width: {Math.round(e.anteil * 100)}%"></span></span>{Math.round(e.anteil * 100)} %</span>
              {/snippet}
            </Kachel>
          {/each}
        </div>
        {/if}
      </section>
    {/if}

    {#if meins.merkzettel.length}
      <section class="merkzettel">
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-bookmark"></i>Merkzettel</h2><span class="neben">{meins.merkzettel.length}</span>
          <button class="alle" onclick={() => gehe("merkzettel")}>Alle</button></div>
        <div class="liste">
          {#each meins.merkzettel.slice(0, MERKZETTEL) as m (m.id)}
            <div class="liste-zeile">
              <button class="liste-ziel" disabled={!m.buch} onclick={() => lesen(m.buch, m.pfad)}>
                {#if m.bild}<img src={m.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-bookmark"></i></span>{/if}
                <span><span class="t">{m.titel}</span><span class="u">gemerkt {wann(m.angelegt)}</span></span>
                <span class="rechts">{m.anteil > 0 ? `${Math.round(m.anteil * 100)} %` : "ungelesen"}</span>
              </button>
            </div>
          {/each}
        </div>
      </section>
    {/if}

    {#if magazin && themaReihe?.eintraege.length}
      <section class="thema-reihe">
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-layer-group"></i>Aus deinem Thema {themaReihe.titel}</h2>
          <button class="alle" onclick={() => heute && gehe(`themen/${heute.thema_id}`)}>Zum Thema</button></div>
        <div class="reihe">
          {#each themaReihe.eintraege as e (e.pfad)}
            <Kachel bild={e.bild} titel={e.titel} untertitel={e.anteil > 0 ? `${Math.round(e.anteil * 100)} % gelesen` : "noch nicht gelesen"}
                    ziel={() => lesen(e.buch, e.pfad)} />
          {/each}
        </div>
      </section>
    {/if}

    {#if mitLesedesign.length}
      <section class="stoebern-abschnitt">
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-shuffle"></i>Stöbern</h2><button class="alle" onclick={() => gehe("stoebern")}>Mehr stöbern</button></div>
        <div class="stoebern">
          {#each mitLesedesign as b (b.kennung)}
            {@const f = funde[b.kennung]}
            <Kachel art="text" titel={f?.titel ?? "sucht ..."} untertitel={b.titel}>
              {#snippet vorsatz()}<span class="fund-etikett"><i class="fa-solid fa-dice"></i>Zufallsfund</span>{/snippet}
              {#snippet ecke()}<Sprachmarke kuerzel={b.sprache} />{/snippet}
              {#if f?.einleitung}<span class="auszug">{f.einleitung}</span>{/if}
              {#snippet fuss()}
                <span class="knopfreihe">
                  <button class="knopf" disabled={!f} onclick={() => f && lesen(b.kennung, f.pfad)}><i class="fa-solid fa-book-open"></i>Lesen</button>
                  <button class="knopf still" onclick={() => zufallsfund(b)}><i class="fa-solid fa-rotate"></i>Neuer Zufall</button>
                </span>
              {/snippet}
            </Kachel>
          {/each}
        </div>
      </section>
    {/if}

    <section>
      <div class="abschnitt-kopf"><h2><i class="fa-solid fa-swatchbook"></i>Bibliothek</h2>
        <span class="neben">{aktive.length} {aktive.length === 1 ? "Quelle" : "Quellen"}</span>
        <button class="alle" onclick={() => gehe("bibliothek")}>Verwalten</button></div>
      {#if lader.stand?.neu_ungesehen}
        <div class="fundband"><i class="fa-solid fa-star"></i>
          <span>Im Verzeichnis der Bücher ist Neues: {lader.stand.neu_ungesehen} {lader.stand.neu_ungesehen === 1 ? "Buch oder Fassung" : "Bücher und Fassungen"}
            seit der letzten Durchsicht.</span>
          <button class="knopf" onclick={() => gehe("bibliothek/katalog")}>Ansehen</button></div>
      {/if}
      {#if lader.stand?.abos.some((a) => a.zustand === "wartet_auf_umschalten")}
        <div class="fundband"><i class="fa-solid fa-right-left"></i>
          <span>Neue Fassungen sind geladen und geprüft und warten aufs Umschalten.</span>
          <button class="knopf" onclick={() => gehe("bibliothek/laden")}>Fassungen</button></div>
      {/if}
      {#if bibliothek.meldung}<div class="fehlertext">{bibliothek.meldung}</div>{/if}
      {#if bibliothek.geladen && !bibliothek.buecher.length && !bibliothek.meldung}
        <p class="leer-hinweis">Im Ordner der ZIM-Libs liegt noch keine ZIM-Datei. Den Ordner nennen die Einstellungen unter Bibliothek.</p>
      {/if}
      <div class="buecher">
        {#each ordnen(aktive) as e (e.art === "buch" ? e.buch.kennung : e.kennung)}
          {#if e.art === "buch"}<Buchkachel buch={e.buch} />
          {:else}<Buendelebene titel={e.titel} gesamt={e.gesamt} themen={e.themen} />{/if}
        {/each}
      </div>
      {#each bibliothek.fehler as f}<div class="fehlertext buchfehler">{f}</div>{/each}
      {#if bibliothek.buecher.length}
        <!-- Archiv der Quellen (WIKI-46): ältere Fassungen von selbst, andere von Hand; je Quelle mitnutzen oder wieder aktiv -->
        <details class="archiv-block">
          <summary><i class="fa-solid fa-box-archive"></i><b>Archiv</b><span class="zahl">{archivierte.length}</span>
            <span class="neben">ältere Fassungen und Abgelegtes; ohne "Mitnutzen" nicht in Suche und Stöbern, lesbar bleibt alles</span></summary>
          <div class="liste">
            {#each archivierte as b (b.kennung)}
              {@const neu = b.archiv?.ersetzt_durch ? buchVon(b.archiv.ersetzt_durch) : undefined}
              <div class="liste-zeile">
                <button class="liste-ziel" onclick={() => lesen(b.kennung, b.startseite)}>
                  <span class="ohne-bild"><Buchzeichen buch={b} /></span>
                  <span><span class="t">{bezeichnung(b)}</span>
                    <span class="u">Stand {datum(b.stand)} · {b.archiv?.grund === "ersetzt"
                      ? `ersetzt durch die Fassung ${neu ? `vom ${datum(neu.stand)}` : b.archiv.ersetzt_durch}` : "von Hand abgelegt"}</span></span>
                </button>
                <button class="knopf still" class:an={b.archiv?.mitnutzen} title="In Suche, Stöbern und Startseite mitzählen (hinter den aktiven Quellen)"
                        onclick={() => archiv(b.kennung, { mitnutzen: !b.archiv?.mitnutzen })}>
                  <i class="fa-solid {b.archiv?.mitnutzen ? 'fa-toggle-on' : 'fa-toggle-off'}"></i><span class="wort">Mitnutzen</span></button>
                <button class="knopf still" title="Wieder als aktive Quelle führen"
                        onclick={() => archiv(b.kennung, { zustand: b.archiv?.grund === "ersetzt" ? "aktiv" : null })}>
                  <i class="fa-solid fa-box-open"></i><span class="wort">Wieder aktiv</span></button>
              </div>
            {:else}
              <p class="leer-hinweis">Noch nichts im Archiv. Ältere Fassungen einer Quelle kommen von selbst hierher.</p>
            {/each}
          </div>
          {#if aktive.length}
            <div class="archiv-ablegen">
              <Auswahl wert="" symbol="fa-box-archive" titel="Eine aktive Quelle von Hand ins Archiv legen"
                       optionen={[{ wert: "", titel: "Quelle ins Archiv legen" }, ...reihenfolge(aktive).map((b) => ({ wert: b.kennung, titel: bezeichnung(b), hinweis: buendelHinweis(b) }))]}
                       onwahl={(k) => k && archiv(k, { zustand: "archiv" })} />
            </div>
          {/if}
          {#if archivFehler}<div class="fehlertext">{archivFehler}</div>{/if}
        </details>
      {/if}
    </section>
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  </div>
</div>
</div>
