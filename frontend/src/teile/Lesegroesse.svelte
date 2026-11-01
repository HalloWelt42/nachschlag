<script lang="ts">
  // Knopf Lesegröße im Artikelkopf: klappt die Stufen auf, für dieses Buch und als Vorgabe für alle Bücher, beides auf
  // diesem Gerät. Schließt bei Klick daneben und mit Escape.
  import { buchSetzen, groesseFuer, lesegroesse, naechste, STUFEN, vorgabeSetzen } from "../lib/lesegroesse.svelte";

  let { buchName, buchTitel }: { buchName: string; buchTitel: string } = $props();

  let offen = $state(false);
  let wurzel: HTMLElement;

  const jetzt = $derived(groesseFuer(buchName));
  const eigene = $derived(lesegroesse.buecher[buchName] !== undefined);
  const ERSTE = STUFEN[0], LETZTE = STUFEN[STUFEN.length - 1];
</script>

<svelte:window onclick={(e) => offen && !wurzel.contains(e.target as Node) && (offen = false)}
               onkeydown={(e) => e.key === "Escape" && (offen = false)} />
<div class="lesegroesse" bind:this={wurzel}>
  <button class="rund" class:an={jetzt !== 100} title="Lesegröße: {jetzt} %" aria-expanded={offen} onclick={() => (offen = !offen)}>
    <i class="fa-solid fa-text-height"></i></button>
  {#if offen}
    <div class="lesegroesse-tafel" role="dialog" aria-label="Lesegröße">
      <div class="groesse-zeile">
        <span class="was"><b>{buchTitel}</b>{eigene ? "eigene Größe" : "wie alle Bücher"}</span>
        <button class="rund" title="Kleiner" disabled={jetzt <= ERSTE} onclick={() => buchSetzen(buchName, naechste(jetzt, -1))}><i class="fa-solid fa-minus"></i></button>
        <span class="wert">{jetzt} %</span>
        <button class="rund" title="Größer" disabled={jetzt >= LETZTE} onclick={() => buchSetzen(buchName, naechste(jetzt, 1))}><i class="fa-solid fa-plus"></i></button>
      </div>
      <div class="groesse-zeile">
        <span class="was"><b>Alle Bücher</b>Vorgabe</span>
        <button class="rund" title="Kleiner" disabled={lesegroesse.vorgabe <= ERSTE} onclick={() => vorgabeSetzen(naechste(lesegroesse.vorgabe, -1))}><i class="fa-solid fa-minus"></i></button>
        <span class="wert">{lesegroesse.vorgabe} %</span>
        <button class="rund" title="Größer" disabled={lesegroesse.vorgabe >= LETZTE} onclick={() => vorgabeSetzen(naechste(lesegroesse.vorgabe, 1))}><i class="fa-solid fa-plus"></i></button>
      </div>
      <div class="groesse-fuss">
        <span>Gilt auf diesem Gerät.</span>
        {#if eigene}<button class="knopf still" onclick={() => buchSetzen(buchName, null)}>Wie alle Bücher</button>{/if}
      </div>
    </div>
  {/if}
</div>
