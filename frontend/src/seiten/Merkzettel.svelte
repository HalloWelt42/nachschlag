<script lang="ts">
  // Merkzettel (Entwurf mockups/merkzettel.html): gemerkte Seiten mit Buch, Zeitpunkt und Lesestand; Filter nach
  // Lesestand, Suche im Merkzettel, Entfernen. Gilt auf allen Geräten des Kontos.
  import Buchmarke from "../teile/Buchmarke.svelte";
  import { onMount } from "svelte";
  import { geraet, seitenFehler } from "appkern-oberflaeche";
  import { bibliothekLaden, buchName } from "../lib/bibliothek.svelte";
  import { meins, meinsLaden, vergessen, wann, type Merkeintrag } from "../lib/meins.svelte";
  import { lesen } from "../lib/ziele";

  type Filter = "alle" | "ungelesen" | "angefangen" | "gelesen";
  const GELESEN_AB = 0.95;

  let filter = $state<Filter>("alle");
  let suche = $state("");
  let fehler = $state("");

  const art = (m: Merkeintrag): Exclude<Filter, "alle"> => (m.anteil >= GELESEN_AB ? "gelesen" : m.anteil > 0 ? "angefangen" : "ungelesen");
  const zahlen = $derived({ alle: meins.merkzettel.length, ...Object.fromEntries((["ungelesen", "angefangen", "gelesen"] as const)
    .map((f) => [f, meins.merkzettel.filter((m) => art(m) === f).length])) } as Record<Filter, number>);
  const liste = $derived(meins.merkzettel.filter((m) => (filter === "alle" || art(m) === filter)
    && (!suche.trim() || `${m.titel} ${m.abschnitt}`.toLowerCase().includes(suche.trim().toLowerCase()))));

  async function entfernen(m: Merkeintrag) {
    try {
      await vergessen(m.id);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  onMount(() => {
    void bibliothekLaden();              // Namen der Bücher statt Kennungen
    void meinsLaden(true);
  });
</script>

<div class="inhalt-stufe" data-schrift="klein">
  <div class="rollfeld" style="padding: 0">
    <div class="meins-seite">
      <div class="meins-kopf">
        {#if !geraet.mobil}<h1>Merkzettel</h1>{/if}          <!-- am Telefon steht der Titel im Kopf -->
        <div class="segment meins-filter">
          {#each (["alle", "ungelesen", "angefangen", "gelesen"] as const) as f (f)}
            <button class:aktiv={filter === f} onclick={() => (filter = f)}>{f === "alle" ? "Alle" : f[0].toUpperCase() + f.slice(1)} {zahlen[f]}</button>
          {/each}
        </div>
        <label class="suchfeld meins-suche"><i class="fa-solid fa-magnifying-glass"></i>
          <input name="suche" type="search" placeholder="Im Merkzettel suchen" bind:value={suche} aria-label="Im Merkzettel suchen" /></label>
      </div>
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      {#if meins.geladen && !meins.merkzettel.length}
        <p class="leer-hinweis">Noch nichts gemerkt. Im Artikel oben "Merken" wählen; der Merkzettel gilt auf allen deinen Geräten.</p>
      {/if}
      <div class="liste">
        {#each liste as m (m.id)}
          <div class="liste-zeile">
            <button class="liste-ziel" disabled={!m.buch} onclick={() => lesen(m.buch, m.pfad)}
                    title={m.buch ? "Öffnen" : "Die Quelle gibt es nicht mehr in der Bibliothek"}>
              {#if m.bild}<img src={m.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-bookmark"></i></span>{/if}
              <span><span class="t">{m.titel}{m.abschnitt ? ` › ${m.abschnitt}` : ""}</span>
                <span class="u"><Buchmarke kennung={m.buch} ersatz={m.buch_name} symbol={false} /> · gemerkt {wann(m.angelegt)}</span></span>
              <span class="rechts">{art(m) === "angefangen" ? `${Math.round(m.anteil * 100)} %` : art(m)}</span>
            </button>
            <button class="rund" title="Vom Merkzettel nehmen" onclick={() => entfernen(m)}><i class="fa-solid fa-xmark"></i></button>
          </div>
        {/each}
      </div>
    </div>
  </div>
</div>
