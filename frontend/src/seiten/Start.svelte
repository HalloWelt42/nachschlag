<script lang="ts">
  // Startseite, Variante A (Entwurf mockups/start-a.html): Suche in der Mitte, darunter Stöbern mit einem Zufallsfund
  // je Buch mit Lesedesign und die Bibliothek mit ihren Büchern und Fähigkeiten.
  import { onMount } from "svelte";
  import { seitenFehler } from "appkern-oberflaeche";
  import Suchfeld from "../teile/Suchfeld.svelte";
  import Kachel from "../teile/Kachel.svelte";
  import Sprachmarke from "../teile/Sprachmarke.svelte";
  import { bibliothek, bibliothekLaden, datum, zahl } from "../lib/bibliothek.svelte";
  import { artikelHolen, zufallHolen } from "../lib/schnittstelle";
  import type { Art, Buch } from "../lib/typen";
  import { lesen } from "../lib/ziele";
  import { gehe } from "appkern-oberflaeche";
  import { meins, meinsLaden, verlaufHolen, wann, type Verlaufseintrag } from "../lib/meins.svelte";

  const WEITERLESEN = 4;                 // Karten im Entwurf
  const MERKZETTEL = 5;
  const FERTIG_AB = 0.95;                // so weit gelesen gilt als fertig, nicht mehr zum Weiterlesen
  let weiterlesen = $state.raw<Verlaufseintrag[]>([]);

  interface Fund { buch: Buch; pfad: string; titel: string; einleitung: string }

  const SYMBOL: Record<Art, string> = { enzyklopaedie: "fa-book", dokumentation: "fa-code", frage_antwort: "fa-comments",
                                       webseite: "fa-globe", sonstiges: "fa-box-archive" };

  let funde = $state<Record<string, Fund | null>>({});
  let fehler = $state("");

  const artikelGesamt = $derived(bibliothek.buecher.reduce((s, b) => s + b.artikel, 0));
  const mitLesedesign = $derived(bibliothek.buecher.filter((b) => b.faehigkeiten.lesedesign));

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
  <div class="start-innen">
    <div class="suchmitte">
      <h1>Was möchtest du nachschlagen?</h1>
      <Suchfeld gross />
      {#if bibliothek.buecher.length}
        <div class="unter">Index über <span class="zahl">{zahl(artikelGesamt)}</span> Artikel in {bibliothek.buecher.length}
          {bibliothek.buecher.length === 1 ? "Quelle" : "Quellen"}</div>
      {/if}
    </div>

    {#if weiterlesen.length}
      <section>
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-book-open-reader"></i>Weiterlesen</h2>
          <button class="alle" onclick={() => gehe("verlauf")}>Verlauf</button></div>
        <div class="reihe">
          {#each weiterlesen as e (e.id)}
            <Kachel bild={e.bild} titel={e.titel} untertitel={e.abschnitt ? `bei ${e.abschnitt}` : ""} ziel={() => lesen(e.buch, e.pfad)}>
              {#snippet fuss()}
                <span class="lesestand-fuss"><span class="spur"><span style="width: {Math.round(e.anteil * 100)}%"></span></span>{Math.round(e.anteil * 100)} %</span>
              {/snippet}
            </Kachel>
          {/each}
        </div>
      </section>
    {/if}

    {#if meins.merkzettel.length}
      <section>
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

    {#if mitLesedesign.length}
      <section>
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-shuffle"></i>Stöbern</h2><button class="alle" onclick={() => gehe("stoebern")}>Mehr stöbern</button></div>
        <div class="stoebern">
          {#each mitLesedesign as b (b.kennung)}
            {@const f = funde[b.kennung]}
            <Kachel art="text" titel={f?.titel ?? "sucht ..."} untertitel={b.titel}>
              {#snippet vorsatz()}<span class="etikett"><i class="fa-solid fa-dice"></i>Zufallsfund</span>{/snippet}
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
        <span class="neben">{bibliothek.buecher.length} {bibliothek.buecher.length === 1 ? "Quelle" : "Quellen"}</span></div>
      {#if bibliothek.meldung}<div class="fehlertext">{bibliothek.meldung}</div>{/if}
      {#if bibliothek.geladen && !bibliothek.buecher.length && !bibliothek.meldung}
        <p class="leer-hinweis">Im Ordner der ZIM-Libs liegt noch keine ZIM-Datei. Den Ordner nennen die Einstellungen unter Bibliothek.</p>
      {/if}
      <div class="buecher">
        {#each bibliothek.buecher as b (b.kennung)}
          <Kachel art="quer" symbol={SYMBOL[b.art]} titel={b.titel} untertitel={`${zahl(b.artikel)} Artikel · Stand ${datum(b.stand)}`}
                 hinweis="Startseite der Quelle öffnen" ziel={() => lesen(b.kennung, b.startseite)}>
            {#snippet ecke()}<Sprachmarke kuerzel={b.sprache} />{/snippet}
            {#snippet fuss()}
              <span class="faehig">
                {#if b.faehigkeiten.volltext}<span class="faehigkeit an"><i class="fa-solid fa-check"></i>Index</span>{/if}
                {#if b.faehigkeiten.lesedesign}<span class="faehigkeit an"><i class="fa-solid fa-book-open-reader"></i>Lesedesign</span>
                {:else}<span class="faehigkeit"><i class="fa-solid fa-file-code"></i>Originalansicht</span>{/if}
              </span>
            {/snippet}
          </Kachel>
        {/each}
      </div>
      {#each bibliothek.fehler as f}<div class="fehlertext">{f}</div>{/each}
    </section>
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  </div>
</div>
</div>
