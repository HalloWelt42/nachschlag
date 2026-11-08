<script lang="ts">
  // Große Bildansicht (Entwurf mockups/medien.html): das Bild, Pfeile und Tasten zum Blättern, darunter der Streifen der
  // übrigen Bilder, rechts die Angaben (Artikel, Abschnitt, Größe, Datei) mit "Im Artikel zeigen" und Thema. Escape
  // schließt. Die Bücher bringen meist nur Vorschaubilder mit; die Ansicht zeigt das ehrlich bei der Größe.
  // Telefon (WIKI-27, WIKI-69): nur das Bild über den ganzen Schirm, Angaben und Streifen hinter dem Knopf Info;
  // Wischen blättert. Vergrößern überall (Zoombild): zwei Finger, Doppeltippen, Mausrad; vergrößert verschiebt der
  // Finger das Bild statt zu blättern. Hat der Bildholer das große Bild schon geholt (WIKI-80), zeigt die Ansicht es mit
  // Urheber und Lizenz; sonst das Vorschaubild aus dem Buch.
  import { onMount, tick } from "svelte";
  import { bibliothekLaden, buch as buchVon } from "../lib/bibliothek.svelte";
  import { themenLaden } from "../lib/themen.svelte";
  import { grossAdresse, grossAngaben, type Grossangaben, type Medium } from "../lib/medien";
  import { lesen } from "../lib/ziele";
  import ThemaWahl from "./ThemaWahl.svelte";
  import Zoombild from "./Zoombild.svelte";

  let { medien, start = 0, titel = "", onzu }: { medien: Medium[]; start?: number; titel?: string; onzu: () => void } = $props();

  const WISCHEN_AB_PX = 50;

  let index = $state(0);
  let vergroessert = $state(false);                    // das Zoombild gehört dann dem Finger, Wischen blättert nicht
  let angaben = $state(false);                         // Telefon: Angaben und Streifen sichtbar
  let wischStart: { x: number; y: number } | null = null;

  function wischBeginn(e: PointerEvent) {
    wischStart = e.pointerType !== "mouse" && e.isPrimary ? { x: e.clientX, y: e.clientY } : null;
  }
  function wischEnde(e: PointerEvent) {
    if (!wischStart || vergroessert || !e.isPrimary) return (wischStart = null);
    const dx = e.clientX - wischStart.x, dy = e.clientY - wischStart.y;
    wischStart = null;
    if (Math.abs(dx) > WISCHEN_AB_PX && Math.abs(dx) > Math.abs(dy) * 1.5) void gehe(index + (dx < 0 ? 1 : -1));
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
  let gross = $state<Grossangaben | null>(null);
  $effect(() => {
    const bild = m?.bild ?? "";
    gross = null;
    if (bild) void grossAngaben(bild).then((g) => { if (m?.bild === bild) gross = g; });
  });
  const zahl = (n: number) => n.toLocaleString("de-DE");
  const buch = $derived(m ? buchVon(m.buch) : undefined);

  async function gehe(neu: number) {
    if (!medien.length) return;
    index = (neu + medien.length) % medien.length;
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
  <div class="leuchtkasten" class:mit-angaben={angaben} role="dialog" aria-modal="true" aria-label="Bild: {m.unterschrift || m.datei}">
    <div class="buehne-b">
      <div class="oben">
        <button class="rund" title="Schließen (Escape)" onclick={onzu}><i class="fa-solid fa-xmark"></i></button>
        <span class="zaehler">{index + 1} von {medien.length} Bildern{titel ? ` ${titel}` : ""}</span>
        <button class="rund lk-info" class:aktiv={angaben} title="Angaben zum Bild" aria-label="Angaben zum Bild" aria-pressed={angaben}
                onclick={() => (angaben = !angaben)}><i class="fa-solid fa-circle-info"></i></button>
      </div>
      <div class="bild-b" onpointerdown={wischBeginn} onpointerup={wischEnde} role="presentation">
        {#if medien.length > 1}<button class="pfeil l" title="Voriges (Pfeil links)" onclick={() => gehe(index - 1)}><i class="fa-solid fa-chevron-left"></i></button>{/if}
        <Zoombild src={gross ? grossAdresse(m.bild) : m.bild} alt={m.unterschrift} bind:vergroessert />
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
        {#if gross}
          <dt>Größe</dt><dd>{zahl(gross.breite)} x {zahl(gross.hoehe)} Pixel, groß aus der Bildquelle (Original {zahl(gross.original)} Pixel breit)</dd>
          {#if gross.urheber}<dt>Urheber</dt><dd>{gross.urheber}</dd>{/if}
          {#if gross.lizenz}<dt>Lizenz</dt><dd>{#if gross.lizenz_url}<a href={gross.lizenz_url} target="_blank" rel="noopener noreferrer">{gross.lizenz}</a>{:else}{gross.lizenz}{/if}</dd>{/if}
        {:else if m.breite}<dt>Größe</dt><dd>{m.breite} x {m.hoehe} Pixel, wie in der Quelle</dd>{/if}
        <dt>Datei</dt><dd class="datei">{m.datei}</dd>
      </dl>
      <div class="angaben-knoepfe">
        <button class="knopf" onclick={imArtikel}><i class="fa-solid fa-book-open"></i>Im Artikel zeigen</button>
        {#if buch}<ThemaWahl artikel={{ buch: m.buch, pfad: m.pfad, titel: m.artikel, bild: m.bild }} buchName={buch.name} />{/if}
      </div>
    </aside>
  </div>
{/if}
