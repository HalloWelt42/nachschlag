<script lang="ts">
  // Themen (Entwurf mockups/themen.html): links die Themen des Kontos mit Bildern und Zahlen, rechts das gewählte Thema.
  // Weg: /themen/<kennung>. Am Telefon erst die Liste, dann das Thema allein (Zurück im Kopf der Schale). Als Buch
  // (WIKI-45) nimmt die ganze Fläche: /themen/<kennung>/buch, .../buch/probe und .../buch/vorlagen.
  import { onMount } from "svelte";
  import { geraet, gehe, navigation, seitenFehler } from "appkern-oberflaeche";
  import { themaAnlegen, themen, themenLaden } from "../lib/themen.svelte";
  import ThemaSeite from "../teile/ThemaSeite.svelte";
  import AlsBuch from "../teile/AlsBuch.svelte";
  import Probekapitel from "../teile/Probekapitel.svelte";
  import Vorlagen from "../teile/Vorlagen.svelte";

  const BILDER = 4;

  let neu = $state<string | null>(null);
  let fehler = $state("");

  const gewaehlt = $derived(navigation.teile[0] ?? "");
  const alsBuch = $derived(navigation.teile[1] === "buch" ? (navigation.teile[2] ?? "") : null);

  // Am Rechner ohne Wahl das erste Thema zeigen (am Telefon bleibt die Liste)
  $effect(() => {
    if (!gewaehlt && !geraet.mobil && themen.liste.length) gehe(`themen/${themen.liste[0].id}`, true);
  });

  async function anlegen() {
    const titel = neu?.trim();
    if (!titel) return;
    try {
      const t = await themaAnlegen(titel);
      neu = null;
      gehe(`themen/${t.id}`);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  function art(k: (typeof themen.liste)[number]): string {
    const teile = [k.bereiche ? `${k.bereiche} ${k.bereiche === 1 ? "Bereich" : "Bereiche"}` : "ohne Bereiche"];
    if (k.buecher > 1) teile.push(`aus ${k.buecher} Quellen`);
    return teile.join(" · ");
  }

  onMount(() => void themenLaden(true));
</script>

<div class="inhalt-stufe" data-schrift="klein">
  {#if gewaehlt && alsBuch !== null}
    {#if alsBuch === "probe"}<Probekapitel thema={gewaehlt} />
    {:else if alsBuch === "vorlagen"}<Vorlagen thema={gewaehlt} />
    {:else}<AlsBuch thema={gewaehlt} />{/if}
  {:else}
  <div class="themen-seite" class:mit-thema={!!gewaehlt}>
    <aside class="themenliste">
      <div class="themen-kopfzeile">
        {#if !geraet.mobil}<h1>Themen</h1>{/if}          <!-- am Telefon steht der Titel im Kopf -->
        <button class="knopf primaer" onclick={() => (neu = "")}><i class="fa-solid fa-plus"></i>Neu</button>
      </div>
      <div class="rollfeld">
        {#if neu !== null}
          <form class="bereich-neu thema-neu" onsubmit={(e) => { e.preventDefault(); void anlegen(); }}>
            <!-- svelte-ignore a11y_autofocus -->
            <input name="neu" class="eingabe" bind:value={neu} placeholder="Name des Themas" maxlength="120" autofocus onkeydown={(e) => e.key === "Escape" && (neu = null)} />
            <button class="knopf primaer" disabled={!neu.trim()}>Anlegen</button>
          </form>
        {/if}
        {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
        {#if themen.geladen && !themen.liste.length && neu === null}
          <p class="leer-hinweis">Noch keine Themen. Ein Thema sammelt Artikel aus allen Quellen, auf Wunsch in Bereichen und mit einer Suche, die neue Treffer vorschlägt.</p>
        {/if}
        {#each themen.liste as k (k.id)}
          <button class="thema-eintrag" class:aktiv={k.id === gewaehlt} onclick={() => gehe(`themen/${k.id}`)}>
            <span class="mini">
              {#each Array.from({ length: BILDER }, (_, i) => k.bilder[i]) as bild, i (i)}
                {#if bild}<img src={bild} alt="" loading="lazy" />{:else}<span></span>{/if}
              {/each}
            </span>
            <span><span class="t">{k.titel}</span><span class="u"><span class="zahl">{k.eintraege}</span> Artikel · {art(k)}</span></span>
          </button>
        {/each}
      </div>
    </aside>
    <div class="thema-flaeche">
      {#if gewaehlt}
        <ThemaSeite id={gewaehlt} ongeloescht={() => gehe("themen", true)} />
      {:else if themen.geladen && !themen.liste.length}
        <p class="leer-hinweis thema-leer">Links "Neu" wählen, oder im Artikel oben "Thema".</p>
      {/if}
    </div>
  </div>
  {/if}
</div>
