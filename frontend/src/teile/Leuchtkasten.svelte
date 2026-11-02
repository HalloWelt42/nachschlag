<script lang="ts">
  // Große Bildansicht (Entwurf mockups/medien.html): das Bild, Pfeile und Tasten zum Blättern, darunter der Streifen der
  // übrigen Bilder, rechts die Angaben (Artikel, Abschnitt, Größe, Datei) mit "Im Artikel zeigen" und Thema. Escape
  // schließt. Die Bücher bringen meist nur Vorschaubilder mit; die Ansicht zeigt das ehrlich bei der Größe.
  // Telefon (WIKI-27): Wischen blättert; quer gedreht nur das Bild über den ganzen Schirm; Tippen vergrößert auf die
  // volle Auflösung, wenn das Bild mehr hat, als der Schirm zeigt (sonst tut Tippen nichts).
  import { onMount, tick } from "svelte";
  import { bibliothekLaden, buch as buchVon } from "../lib/bibliothek.svelte";
  import { themenLaden } from "../lib/themen.svelte";
  import type { Medium } from "../lib/medien";
  import { lesen } from "../lib/ziele";
  import ThemaWahl from "./ThemaWahl.svelte";

  let { medien, start = 0, titel = "", onzu }: { medien: Medium[]; start?: number; titel?: string; onzu: () => void } = $props();

  const WISCHEN_AB_PX = 50;

  let index = $state(0);
  let gross = $state(false);                           // volle Auflösung, rollbar
  let bildEl = $state<HTMLImageElement>();
  let wischStart: { x: number; y: number } | null = null;

  function wischBeginn(e: PointerEvent) {
    if (e.pointerType !== "mouse") wischStart = { x: e.clientX, y: e.clientY };
  }
  function wischEnde(e: PointerEvent) {
    if (!wischStart || gross) return (wischStart = null);
    const dx = e.clientX - wischStart.x, dy = e.clientY - wischStart.y;
    wischStart = null;
    if (Math.abs(dx) > WISCHEN_AB_PX && Math.abs(dx) > Math.abs(dy) * 1.5) void gehe(index + (dx < 0 ? 1 : -1));
  }
  /** Tippen vergrößert nur, wenn die Datei mehr Pixel hat, als gerade zu sehen sind. */
  function antippen() {
    if (gross) return (gross = false);
    if (bildEl && bildEl.naturalWidth > bildEl.clientWidth * 1.2) gross = true;
  }
  let streifen = $state<HTMLElement>();
  let fehlen = $state<Record<string, true>>({});        // Bilder, die nicht laden, bleiben aus dem Streifen

  onMount(() => {
    void bibliothekLaden();                             // Buch und Themen für "Thema" in den Angaben
    void themenLaden();
  });

  $effect.pre(() => {
    index = Math.min(Math.max(start, 0), medien.length - 1);
  });

  const m = $derived(medien[index]);
  const buch = $derived(m ? buchVon(m.buch) : undefined);

  async function gehe(neu: number) {
    if (!medien.length) return;
    index = (neu + medien.length) % medien.length;
    gross = false;
    await tick();
    streifen?.querySelector(".an")?.scrollIntoView({ block: "nearest", inline: "center" });
  }

  function taste(e: KeyboardEvent) {
    if (e.key === "Escape") onzu();
    else if (e.key === "ArrowRight") void gehe(index + 1);
    else if (e.key === "ArrowLeft") void gehe(index - 1);
    else return;
    e.preventDefault();
  }

  function imArtikel() {
    if (!m) return;
    lesen(m.buch, m.pfad, m.abschnitt ? { abschnitt: m.abschnitt } : {});
    onzu();
  }
</script>

<!-- in der Fangphase: die Bildansicht nimmt ihre Tasten vor der Leiste darunter (Escape schließt nur sie) -->
<svelte:window onkeydowncapture={taste} />
{#if m}
  <div class="leuchtkasten" role="dialog" aria-modal="true" aria-label="Bild: {m.unterschrift || m.datei}">
    <div class="buehne-b">
      <div class="oben">
        <button class="rund" title="Schließen (Escape)" onclick={onzu}><i class="fa-solid fa-xmark"></i></button>
        <span class="zaehler">{index + 1} von {medien.length} Bildern{titel ? ` ${titel}` : ""}</span>
      </div>
      <div class="bild-b">
        {#if medien.length > 1}<button class="pfeil l" title="Voriges (Pfeil links)" onclick={() => gehe(index - 1)}><i class="fa-solid fa-chevron-left"></i></button>{/if}
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
        <img bind:this={bildEl} class:gross src={m.bild} alt={m.unterschrift} onclick={antippen} onpointerdown={wischBeginn} onpointerup={wischEnde}
             title={gross ? "Wieder einpassen" : "Tippen: größer, wenn das Bild mehr Auflösung hat"} />
        {#if medien.length > 1}<button class="pfeil r" title="Nächstes (Pfeil rechts)" onclick={() => gehe(index + 1)}><i class="fa-solid fa-chevron-right"></i></button>{/if}
      </div>
      {#if medien.length > 1}
        <div class="streifen" bind:this={streifen}>
          {#each medien as x, i (x.bild + i)}
            {#if !fehlen[x.bild]}
              <button class:an={i === index} title={x.unterschrift || x.datei} onclick={() => gehe(i)}>
                <img src={x.bild} alt="" loading="lazy" onerror={() => (fehlen = { ...fehlen, [x.bild]: true })} /></button>
            {/if}
          {/each}
        </div>
      {/if}
    </div>
    <aside class="angaben">
      <b class="titel">{m.unterschrift || m.datei}</b>
      <dl>
        <dt>Artikel</dt><dd>{m.artikel}{m.abschnitt ? `, Abschnitt ${m.abschnitt}` : ""}</dd>
        {#if m.breite}<dt>Größe</dt><dd>{m.breite} x {m.hoehe} Pixel, wie in der Quelle</dd>{/if}
        <dt>Datei</dt><dd class="datei">{m.datei}</dd>
      </dl>
      <div class="angaben-knoepfe">
        <button class="knopf" onclick={imArtikel}><i class="fa-solid fa-book-open"></i>Im Artikel zeigen</button>
        {#if buch}<ThemaWahl artikel={{ buch: m.buch, pfad: m.pfad, titel: m.artikel, bild: m.bild }} buchName={buch.name} />{/if}
      </div>
    </aside>
  </div>
{/if}
