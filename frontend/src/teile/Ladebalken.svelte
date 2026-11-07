<script lang="ts">
  // Fortschritt beim Laden eines Buchs (WIKI-57, Nutzer 07.11.2026: "beim Laden neuer Versionen ist eine
  // Fortschrittsanzeige zwingend notwendig"): Balken und der Schritt des Ladeauftrags (Menge, Tempo, Restzeit, Prüfsumme),
  // live aus den Ereignissen der Aufträge. Eine Stelle für Fassungen und Laden, Katalog und Meine Bücher.
  import { ladungen } from "../lib/buecherlader.svelte";

  let { stamm }: { stamm: string } = $props();
  const l = $derived(ladungen[stamm]);
  const prozent = $derived(l?.fortschritt != null ? Math.round(l.fortschritt * 100) : null);
</script>

{#if l}
  <div class="ladebalken" class:wartet={l.zustand === "wartet"}>
    <div class="ladebalken-spur" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={prozent ?? undefined}
         aria-label="Fortschritt beim Laden">
      <span style:width="{prozent ?? 0}%"></span>
    </div>
    <span class="ladebalken-text">
      {#if l.zustand === "wartet"}{l.zurueckgestellt || "wartet, bis das Buch davor fertig ist"}
      {:else}{#if prozent != null}<b>{prozent} %</b> · {/if}{l.schritt || "beginnt"}{/if}
    </span>
  </div>
{/if}
