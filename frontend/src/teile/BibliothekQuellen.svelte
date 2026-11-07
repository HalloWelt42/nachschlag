<script lang="ts">
  // Quellen des Bücherladers (WIKI-62): Verzeichnisse von Spiegeln und Kataloge. Jede Durchsicht liest alle
  // eingeschalteten und bildet daraus die Vereinigungsmenge; geladen wird in dieser Reihenfolge, bei einem Fehler von der
  // nächsten. Hinzufügen von Hand oder aus den Spiegeln der offiziellen Ladedatei.
  import { seitenFehler } from "appkern-oberflaeche";
  import { datum, zahl } from "../lib/bibliothek.svelte";
  import { lader, laderLaden } from "../lib/buecherlader.svelte";
  import { quelleAendern, quelleAnlegen, quelleEntfernen, quellvorschlaegeHolen } from "../lib/schnittstelle";
  import type { Quellstand, Quellvorschlag } from "../lib/typen";

  const ART = { verzeichnis: "Verzeichnis", katalog: "Katalog" } as const;
  const quellen = $derived(lader.stand?.quellen ?? []);

  let art = $state<Quellstand["art"]>("verzeichnis");
  let adresse = $state("");
  let name = $state("");
  let vorschlaege = $state.raw<Quellvorschlag[] | null>(null);
  let fehler = $state("");
  let arbeitet = $state("");

  async function tun(schluessel: string, arbeit: () => Promise<unknown>) {
    arbeitet = schluessel;
    try {
      await arbeit();
      fehler = "";
      await laderLaden(true);
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      arbeitet = "";
    }
  }

  /** Mit dem Nachbarn tauschen: die Reihenfolge ist die Reihenfolge beim Laden. */
  function verschieben(i: number, richtung: -1 | 1) {
    const a = quellen[i], b = quellen[i + richtung];
    if (!a || !b) return;
    void tun(`rang${a.nr}`, async () => {
      await quelleAendern(a.nr, { rang: b.rang });
      await quelleAendern(b.nr, { rang: a.rang === b.rang ? a.rang + richtung : a.rang });
    });
  }

  async function anlegen(neu: { art: Quellstand["art"]; adresse: string; name: string }) {
    await quelleAnlegen(neu.art, neu.adresse.trim(), neu.name.trim());
    adresse = name = "";
    if (vorschlaege) vorschlaege = vorschlaege.filter((v) => v.adresse !== neu.adresse);
  }
</script>

<section class="lade-karte">
  <div class="lade-kopf"><h2><i class="fa-solid fa-sitemap"></i>Quellen</h2>
    <span class="neben">jede Durchsicht liest alle eingeschalteten und führt sie zusammen; geladen wird in dieser Reihenfolge,
      bei einem Fehler von der nächsten</span></div>
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  <div class="quellen-liste">
    {#each quellen as q, i (q.nr)}
      <div class="quelle-zeile" class:aus={!q.an}>
        <button class="chip wahl" class:an={q.an} disabled={!!arbeitet} title={q.an ? "Ausschalten" : "Einschalten"}
                onclick={() => tun(`an${q.nr}`, () => quelleAendern(q.nr, { an: !q.an }))}>
          <i class="fa-solid {q.an ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>{q.an ? "an" : "aus"}</button>
        <span class="quelle-name"><b>{q.name}</b><span class="art-q">{ART[q.art]}</span><code>{q.adresse}</code></span>
        <span class="quelle-stand" class:warn={!!q.meldung}>
          {#if q.meldung}<i class="fa-solid fa-triangle-exclamation"></i>{q.meldung}
          {:else if q.zuletzt}{zahl(q.funde)} Dateien, {datum(q.zuletzt.slice(0, 10))}
          {:else}noch nicht durchgesehen{/if}</span>
        <span class="quelle-knoepfe">
          <button class="rund" title="Früher versuchen" disabled={i === 0 || !!arbeitet} onclick={() => verschieben(i, -1)}>
            <i class="fa-solid fa-arrow-up"></i></button>
          <button class="rund" title="Später versuchen" disabled={i === quellen.length - 1 || !!arbeitet} onclick={() => verschieben(i, 1)}>
            <i class="fa-solid fa-arrow-down"></i></button>
          <button class="rund" title="Entfernen" disabled={!!arbeitet} onclick={() => tun(`weg${q.nr}`, () => quelleEntfernen(q.nr))}>
            <i class="fa-solid fa-trash"></i></button>
        </span>
      </div>
    {/each}
  </div>

  <form class="quelle-neu" onsubmit={(e) => { e.preventDefault(); void tun("neu", () => anlegen({ art, adresse, name })); }}>
    <div class="segment" role="radiogroup" aria-label="Art der Quelle">
      <button type="button" class:aktiv={art === "verzeichnis"} onclick={() => (art = "verzeichnis")}>Verzeichnis</button>
      <button type="button" class:aktiv={art === "katalog"} onclick={() => (art = "katalog")}>Katalog</button>
    </div>
    <input class="eingabe" type="url" bind:value={adresse} required placeholder="https://.../zim/" aria-label="Adresse der Quelle" />
    <input class="eingabe quelle-name-feld" bind:value={name} placeholder="Name (wahlweise)" aria-label="Name der Quelle" />
    <button class="knopf" type="submit" disabled={!!arbeitet || !adresse.trim()}><i class="fa-solid fa-plus"></i>Hinzufügen</button>
    <button class="knopf still" type="button" disabled={!!arbeitet}
            onclick={() => tun("vorschlaege", async () => { vorschlaege = await quellvorschlaegeHolen(); })}>
      <i class="fa-solid fa-wand-magic-sparkles"></i>Spiegel vorschlagen</button>
  </form>
  {#if vorschlaege}
    <div class="quellen-liste">
      {#each vorschlaege as v (v.adresse)}
        <div class="quelle-zeile vorschlag-q">
          <span class="quelle-name"><b>{v.name}</b>{#if v.land}<span class="art-q">{v.land.toUpperCase()}</span>{/if}<code>{v.adresse}</code></span>
          <button class="knopf" disabled={!!arbeitet}
                  onclick={() => tun(`vor${v.adresse}`, () => anlegen({ art: "verzeichnis", adresse: v.adresse, name: v.name }))}>
            <i class="fa-solid fa-plus"></i>Hinzufügen</button>
        </div>
      {:else}
        <div class="unter-zeile">Alle Spiegel der offiziellen Ladedatei sind schon Quellen.</div>
      {/each}
    </div>
  {/if}
</section>
