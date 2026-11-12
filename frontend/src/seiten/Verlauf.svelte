<script lang="ts">
  // Verlauf (Entwurf mockups/verlauf.html): Gelesenes und Gesuchtes nach Tagen, jüngstes zuerst, mit Lesestand und
  // Lesezeit; auf allen Geräten des Kontos. Seitenweise (je 50), Suche im Verlauf, Leeren mit Bestätigung im Band.
  import Buchmarke from "../teile/Buchmarke.svelte";
  import { onMount } from "svelte";
  import { geraet, seitenFehler } from "appkern-oberflaeche";
  import { hole } from "appkern-oberflaeche";
  import { bibliothekLaden, buchName } from "../lib/bibliothek.svelte";
  import { verlaufHolen, type Verlaufseintrag } from "../lib/meins.svelte";
  import { lesen, suchen } from "../lib/ziele";

  const JE_SEITE = 50;
  let eintraege = $state.raw<Verlaufseintrag[]>([]);
  let mehr = $state(false);
  let art = $state<"" | "artikel" | "suche">("");
  let suche = $state("");
  let fehler = $state("");
  let leerenFragen = $state(false);

  const tagVon = (iso: string) => new Date(iso).toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
  const uhr = (iso: string) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  const gefiltert = $derived(eintraege.filter((e) => !suche.trim()
    || `${e.titel} ${e.frage} ${e.abschnitt}`.toLowerCase().includes(suche.trim().toLowerCase())));
  const tage = $derived.by(() => {
    const gruppen: { tag: string; eintraege: Verlaufseintrag[]; minuten: number }[] = [];
    for (const e of gefiltert) {
      const tag = tagVon(e.zuletzt);
      if (gruppen.at(-1)?.tag !== tag) gruppen.push({ tag, eintraege: [], minuten: 0 });
      gruppen.at(-1)!.eintraege.push(e);
      gruppen.at(-1)!.minuten += e.sekunden / 60;
    }
    return gruppen;
  });

  async function laden(neu: boolean) {
    try {
      const seite = await verlaufHolen(JE_SEITE, neu ? 0 : eintraege.length, art);
      eintraege = neu ? seite : [...eintraege, ...seite];
      mehr = seite.length === JE_SEITE;
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  async function leeren() {
    await hole("/meins/verlauf", { method: "DELETE" });
    leerenFragen = false;
    await laden(true);
  }

  onMount(() => {
    void bibliothekLaden();              // Namen der Bücher statt Kennungen
    void laden(true);
  });
</script>

<div class="inhalt-stufe" data-schrift="klein">
  <div class="rollfeld" style="padding: 0">
    <div class="meins-seite">
      <div class="meins-kopf">
        {#if !geraet.mobil}<h1>Verlauf</h1>{/if}          <!-- am Telefon steht der Titel im Kopf -->
        <div class="segment meins-filter">
          {#each ([["", "Alles"], ["artikel", "Gelesen"], ["suche", "Suchen"]] as const) as [wert, name] (wert)}
            <button class:aktiv={art === wert} onclick={() => { art = wert; void laden(true); }}>{name}</button>
          {/each}
        </div>
        <label class="suchfeld meins-suche"><i class="fa-solid fa-magnifying-glass"></i>
          <input name="suche" type="search" placeholder="Im Verlauf suchen" bind:value={suche} aria-label="Im Verlauf suchen" /></label>
        <button class="knopf still" onclick={() => (leerenFragen = true)}><i class="fa-solid fa-trash"></i>Leeren</button>
      </div>
      {#if leerenFragen}
        <div class="fundband warn"><i class="fa-solid fa-triangle-exclamation"></i>
          <span>Den ganzen Verlauf auf allen Geräten löschen? Merkzettel und Notizen bleiben.</span>
          <button class="knopf" onclick={leeren}>Löschen</button><button class="knopf still" onclick={() => (leerenFragen = false)}>Behalten</button></div>
      {/if}
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      {#if !eintraege.length}<p class="leer-hinweis">Noch nichts gelesen oder gesucht.</p>{/if}
      {#each tage as t (t.tag)}
        <section class="verlauf-tag">
          <h2>{t.tag}<span class="neben">{t.eintraege.length} {t.eintraege.length === 1 ? "Eintrag" : "Einträge"}{t.minuten >= 1 ? ` · ${Math.round(t.minuten)} Minuten gelesen` : ""}</span></h2>
          <div class="liste">
            {#each t.eintraege as e (e.id)}
              <div class="liste-zeile">
                {#if e.art === "suche"}
                  <button class="liste-ziel" onclick={() => suchen(e.frage)}>
                    <span class="ohne-bild"><i class="fa-solid fa-magnifying-glass"></i></span>
                    <span><span class="t">"{e.frage}"</span><span class="u">Suche · {e.treffer} Treffer · {uhr(e.zuletzt)}</span></span>
                    <span class="rechts">Erneut suchen</span>
                  </button>
                {:else}
                  <button class="liste-ziel" disabled={!e.buch} onclick={() => lesen(e.buch, e.pfad)}>
                    {#if e.bild}<img src={e.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-file-lines"></i></span>{/if}
                    <span><span class="t">{e.titel}{e.abschnitt ? ` › ${e.abschnitt}` : ""}</span>
                      <span class="u"><Buchmarke kennung={e.buch} ersatz={e.buch_name} symbol={false} /> · {uhr(e.zuletzt)}</span></span>
                    <span class="rechts">{Math.round(e.anteil * 100)} %{e.sekunden >= 60 ? ` · ${Math.round(e.sekunden / 60)} Min` : ""}</span>
                  </button>
                {/if}
              </div>
            {/each}
          </div>
        </section>
      {/each}
      {#if mehr}<button class="knopf" onclick={() => laden(false)}><i class="fa-solid fa-chevron-down"></i>Ältere laden</button>{/if}
    </div>
  </div>
</div>
