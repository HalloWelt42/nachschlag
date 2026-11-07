<script lang="ts">
  // Gerät, Kategorie und Startseite eines Anleitungsbuchs (iFixit, WIKI-64; Entwurf ifixit-geraet.html). Kopf mit Bild,
  // Kurzbeschreibung und Zahlen; eine Kategorie zeigt ihre Unterkategorien als Bildkacheln, ein Gerät seine Anleitungen
  // (empfohlene vorn, mit Marke), dazu die Werkzeuge und die Beschreibung. Auf der Startseite stehen die hervorgehobenen
  // Kategorien groß mit Bild, die übrigen als Textkacheln (wie in der Quelle). `start`: Inhalt der Startseite davor.
  import type { Snippet } from "svelte";
  import type { Artikel, Geraeteeintrag } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";
  import Kachel from "./Kachel.svelte";

  let { artikel, start }: { artikel: Artikel; start?: Snippet } = $props();
  const g = $derived(artikel.geraet!);
  const hervor = $derived(g.unterkategorien.filter((e) => e.empfohlen && e.bild));
  const uebrige = $derived(g.unterkategorien.filter((e) => !(e.empfohlen && e.bild)));
  const anleitungen = $derived([...g.anleitungen].sort((x, y) => Number(y.empfohlen) - Number(x.empfohlen)));
  const ziel = (e: Geraeteeintrag) => "/" + lesenZiel(artikel.buch, e.pfad);
</script>

<div class="rollfeld" style="padding: 0">
  <div class="anl-geraet">
    {#if start}{@render start()}{/if}
    {#if artikel.darstellung === "geraet"}
      <div class="anl-g-kopf" class:ohne-bild={!g.bild}>
        {#if g.bild}<img src={g.bild} alt="" />{/if}
        <div>
          {#if g.kurz}<p class="anl-g-kurz">{g.kurz}</p>{/if}
          <div class="kennzahlen-reihe">
            {#if g.unterkategorien.length}<div class="kennzahl"><span class="k">Unterkategorien</span><span class="w">{g.unterkategorien.length}</span></div>{/if}
            {#if g.anleitungen.length}<div class="kennzahl"><span class="k">Anleitungen</span><span class="w">{g.anleitungen.length}</span></div>{/if}
            {#if g.werkzeuge.length}<div class="kennzahl"><span class="k">Werkzeuge</span><span class="w">{g.werkzeuge.length}</span></div>{/if}
          </div>
        </div>
      </div>
    {/if}

    {#if hervor.length}
      <section class="anl-g-abschnitt">
        <div class="anl-kacheln gross">
          {#each hervor as e (e.pfad)}<Kachel bild={e.bild} titel={e.titel} adresse={ziel(e)} ziel={() => lesen(artikel.buch, e.pfad)} />{/each}
        </div>
      </section>
    {/if}
    {#if uebrige.length}
      <section class="anl-g-abschnitt">
        <h2><i class="fa-solid fa-sitemap"></i>{artikel.darstellung === "anleitungen" ? "Alle Kategorien" : `${uebrige.length} Kategorien`}</h2>
        <div class="anl-kacheln" class:text={uebrige.every((e) => !e.bild)}>
          {#each uebrige as e (e.pfad)}
            {#if e.bild}<Kachel bild={e.bild} titel={e.titel} adresse={ziel(e)} ziel={() => lesen(artikel.buch, e.pfad)} />
            {:else}<Kachel art="text" titel={e.titel} adresse={ziel(e)} ziel={() => lesen(artikel.buch, e.pfad)} />{/if}
          {/each}
        </div>
      </section>
    {/if}
    {#if anleitungen.length}
      <section class="anl-g-abschnitt">
        <h2><i class="fa-solid fa-list-check"></i>Anleitungen</h2>
        <div class="anl-kacheln">
          {#each anleitungen as e (e.pfad)}
            <Kachel bild={e.bild} symbol="fa-screwdriver-wrench" titel={e.titel} untertitel={e.kurz && e.kurz !== e.titel ? e.kurz : ""}
                    adresse={ziel(e)} ziel={() => lesen(artikel.buch, e.pfad)}>
              {#snippet ecke()}{#if e.empfohlen}<i class="fa-solid fa-award anl-empfohlen" title="empfohlen"></i>{/if}{/snippet}
            </Kachel>
          {/each}
        </div>
      </section>
    {/if}
    {#if g.werkzeuge.length}
      <section class="anl-g-abschnitt">
        <h2><i class="fa-solid fa-toolbox"></i>Werkzeuge</h2>
        <div class="anl-chips">{#each g.werkzeuge as w (w)}<span class="faehigkeit"><i class="fa-solid fa-screwdriver-wrench"></i>{w}</span>{/each}</div>
      </section>
    {/if}
    {#if artikel.html}
      <section class="anl-g-abschnitt">
        <h2><i class="fa-solid fa-circle-info"></i>{artikel.darstellung === "geraet" ? "Über das Gerät" : "Über das Buch"}</h2>
        <!-- eslint-disable-next-line svelte/no-at-html-tags -- vom Baustein gesäubert (nur erlaubte Elemente und Attribute) -->
        <div class="artikel anl-g-text">{@html artikel.html}</div>
      </section>
    {:else if artikel.darstellung === "anleitungen" && g.kurz}
      <p class="anl-g-kurz">{g.kurz}</p>
    {/if}
  </div>
</div>
