<script lang="ts">
  // Kategorienbaum im Kopf des Lesers (WIKI-95/96, Wahl des Nutzers: Knopf mit Tafel): der Knopf nennt die Zahl der
  // Kategorien der Seite, die Tafel zeigt je Kategorie ihre Oberkategorien und einige andere Seiten darin; alles führt
  // weiter. Bei Frage und Antwort sind die Kategorien die Schlagwörter. Geholt wird erst beim Aufklappen.
  import { seitenFehler } from "appkern-oberflaeche";
  import { zahl } from "../lib/bibliothek.svelte";
  import { kategorienbaumHolen } from "../lib/schnittstelle";
  import type { Kategoriezweig } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";

  let { buch, pfad, anzahl, schlagwoerter = false }: { buch: string; pfad: string; anzahl: number; schlagwoerter?: boolean } = $props();

  const RAND = 16;                       // Abstand der Tafel zum Fensterrand
  const BREITE = 720;

  let offen = $state(false);
  let zweige = $state.raw<Kategoriezweig[] | null>(null);
  let fehler = $state("");
  let geholtFuer = "";
  let wurzel: HTMLElement;
  let knopf: HTMLButtonElement;
  let links = $state(0);
  let hoehe = $state(0);

  const wort = $derived(schlagwoerter ? "Schlagwörter" : "Kategorien");

  async function holen() {
    const fuer = `${buch}/${pfad}`;
    if (geholtFuer === fuer) return;
    geholtFuer = fuer;
    zweige = null;
    fehler = "";
    try {
      const geholt = await kategorienbaumHolen(buch, pfad);
      if (geholtFuer === fuer) zweige = geholt;
    } catch (f) {
      if (geholtFuer === fuer) {
        fehler = seitenFehler(f);
        geholtFuer = "";
      }
    }
  }

  /** Die Tafel bleibt im Fenster: nach links gerückt, wenn der Knopf weit rechts steht, nie breiter als das Fenster. */
  function ausrichten() {
    const r = knopf.getBoundingClientRect();
    const breite = Math.min(BREITE, innerWidth - 2 * RAND);
    links = Math.max(RAND, Math.min(r.left, innerWidth - RAND - breite)) - r.left;
    hoehe = Math.max(200, innerHeight - r.bottom - RAND - 6);
  }

  function umschalten() {
    offen = !offen;
    if (offen) {
      ausrichten();
      void holen();
    }
  }

  // eine andere Seite: die Tafel schließt, der Baum wird beim nächsten Aufklappen neu geholt
  $effect(() => {
    void buch;
    void pfad;
    offen = false;
  });

  function gehen(e: MouseEvent, ziel: string) {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    offen = false;
    lesen(buch, ziel);
  }

  const adresse = (ziel: string) => "/" + lesenZiel(buch, ziel);
  const mehr = (z: Kategoriezweig) => z.seiten.length > 0 && (z.seiten_gesamt === 0 || z.seiten_gesamt > z.seiten.length + 1);
</script>

<svelte:window onclick={(e) => offen && !wurzel.contains(e.target as Node) && (offen = false)}
               onkeydown={(e) => e.key === "Escape" && (offen = false)} onresize={() => offen && ausrichten()} />
<div class="kategorienbaum" bind:this={wurzel}>
  <button class="knopf" class:an={offen} bind:this={knopf} aria-expanded={offen} onclick={umschalten}
          title="{wort} dieser Seite: ihre Oberkategorien und andere Seiten darin">
    <i class="fa-solid {schlagwoerter ? 'fa-tags' : 'fa-folder-tree'}"></i><span class="wort">{wort}</span><span class="zahl">{anzahl}</span>
    <i class="fa-solid fa-chevron-down pfeil"></i></button>
  {#if offen}
    <div class="kategorienbaum-tafel" role="region" aria-label={wort} style:left="{links}px" style:max-height="{hoehe}px">
      {#if fehler}
        <div class="fehlertext">{fehler}</div>
      {:else if !zweige}
        <div class="baum-laedt"><i class="fa-solid fa-circle-notch fa-spin"></i>Holt die {wort} ...</div>
      {:else}
        {#each zweige as z (z.kategorie.pfad)}
          <section class="zweig">
            <div class="zweig-kopf">
              <a class="zweig-name" href={adresse(z.kategorie.pfad)} onclick={(e) => gehen(e, z.kategorie.pfad)}>
                <i class="fa-solid {schlagwoerter ? 'fa-tag' : 'fa-folder'}"></i>{z.kategorie.titel}</a>
              {#if z.seiten_gesamt}<span class="zahl">{zahl(z.seiten_gesamt)}</span>{/if}
              {#if z.ober.length}
                <span class="zweig-ober" title="Darüber">
                  <i class="fa-solid fa-turn-up"></i>
                  {#each z.ober as o, oi (o.pfad)}{oi ? ", " : ""}<a href={adresse(o.pfad)} onclick={(e) => gehen(e, o.pfad)}>{o.titel}</a>{/each}
                </span>
              {/if}
            </div>
            {#if z.unter.length}
              <ul class="zweig-seiten zweig-unter" aria-label="Unterkategorien">
                {#each z.unter as u (u.pfad)}
                  <li><a href={adresse(u.pfad)} onclick={(e) => gehen(e, u.pfad)}><i class="fa-solid fa-folder"></i>{u.titel}</a></li>
                {/each}
                {#if z.unter_gesamt > z.unter.length}
                  <li><a class="zweig-mehr" href={adresse(z.kategorie.pfad)} onclick={(e) => gehen(e, z.kategorie.pfad)}>
                    alle {zahl(z.unter_gesamt)}<i class="fa-solid fa-arrow-right"></i></a></li>
                {/if}
              </ul>
            {/if}
            {#if z.seiten.length}
              <ul class="zweig-seiten">
                {#each z.seiten as s (s.pfad)}
                  <li><a href={adresse(s.pfad)} onclick={(e) => gehen(e, s.pfad)}>{s.titel}</a></li>
                {/each}
                {#if mehr(z)}
                  <li><a class="zweig-mehr" href={adresse(z.kategorie.pfad)} onclick={(e) => gehen(e, z.kategorie.pfad)}>
                    {z.seiten_gesamt ? `alle ${zahl(z.seiten_gesamt)}` : "alle"}<i class="fa-solid fa-arrow-right"></i></a></li>
                {/if}
              </ul>
            {:else if !z.unter.length}
              <div class="zweig-leer">Keine weiteren Seiten darin.</div>
            {/if}
          </section>
        {/each}
      {/if}
    </div>
  {/if}
</div>
