<script lang="ts">
  // Stapelarbeit an einer Sammlung (WIKI-44): das Thema oder ein Bereich daraus übersetzen, vertonen, zusammenfassen
  // oder Lernfragen bilden, jetzt oder heute Nacht. Darunter, was läuft und was fertig ist; die Ergebnisse liegen in der
  // Ablage unter Sammlungen/<Thema>/ (Kellerwolke oder Datenordner). Nie ganze Quellen: nur, was in der Sammlung steht.
  import { Auswahl, hole, seitenFehler } from "appkern-oberflaeche";
  import type { Thema } from "../lib/themen.svelte";
  import { ablageIn } from "../lib/ablage";

  type Arbeit = "uebersetzen" | "vertonen" | "zusammenfassen" | "lernfragen";
  interface Stand {
    auftraege: { auftrag: string; arbeit: Arbeit; zustand: string; anteil: number | null; schritt: string; zurueckgestellt: string }[];
    ergebnisse: { arbeit: Arbeit; inhalt: string; ablage: string; wann: string }[];
  }
  const ARBEITEN: { wert: Arbeit; titel: string; symbol: string }[] = [
    { wert: "uebersetzen", titel: "Übersetzen", symbol: "fa-language" },
    { wert: "vertonen", titel: "Vertonen", symbol: "fa-headphones" },
    { wert: "zusammenfassen", titel: "Zusammenfassen", symbol: "fa-align-left" },
    { wert: "lernfragen", titel: "Lernfragen", symbol: "fa-clone" }];
  const TITEL = Object.fromEntries(ARBEITEN.map((a) => [a.wert, a.titel])) as Record<Arbeit, string>;
  const NACHSEHEN_MS = 4000;

  let { thema }: { thema: Thema } = $props();

  let gewaehlt = $state<Arbeit[]>([]);
  let bereich = $state("");
  let wann = $state<"jetzt" | "nachts">("nachts");
  let stimme = $state("");
  let format = $state<"opus" | "mp3">("opus");
  let stimmen = $state<{ wert: string; titel: string }[]>([]);
  let stand = $state.raw<Stand | null>(null);
  let fehler = $state("");
  let offenesErgebnis = $state<Arbeit | "">("");

  const weg = $derived(`/meins/sammlungen/${encodeURIComponent(thema.id)}`);

  async function laden() {
    try {
      stand = await hole<Stand>(weg);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }
  // Stand beim Öffnen und, solange etwas läuft oder wartet, alle paar Sekunden
  $effect(() => {
    void weg;
    void laden();
    const takt = setInterval(() => { if (stand?.auftraege.length) void laden(); }, NACHSEHEN_MS);
    return () => clearInterval(takt);
  });
  $effect(() => {
    if (!gewaehlt.includes("vertonen") || stimmen.length) return;
    hole<{ wert: string; titel: string }[]>("/meins/sammlungen/stimmen").then((s) => (stimmen = s)).catch(() => {});
  });

  function umschalten(a: Arbeit) {
    gewaehlt = gewaehlt.includes(a) ? gewaehlt.filter((x) => x !== a) : [...gewaehlt, a];
  }

  async function starten() {
    fehler = "";
    try {
      stand = await hole<Stand>(weg, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arbeiten: gewaehlt, bereich: bereich || null, wann, stimme, format }) });
      gewaehlt = [];
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }
</script>

<details class="ueber-nacht">
  <summary><i class="fa-solid fa-moon"></i><b>Über Nacht</b>
    <span class="neben">übersetzen, vertonen, zusammenfassen, Lernfragen: nur für diese Sammlung</span>
    {#if stand?.auftraege.length}<span class="zahl">{stand.auftraege.length} in Arbeit</span>{/if}</summary>
  <div class="nacht-wahl">
    <div class="chips">
      {#each ARBEITEN as a (a.wert)}
        <button class="chip" class:an={gewaehlt.includes(a.wert)} aria-pressed={gewaehlt.includes(a.wert)} onclick={() => umschalten(a.wert)}>
          <i class="fa-solid {a.symbol}"></i>{a.titel}</button>
      {/each}
    </div>
    <div class="nacht-zeile">
      <Auswahl wert={bereich} symbol="fa-folder" titel="Welcher Teil der Sammlung" onwahl={(w) => (bereich = w)}
               optionen={[{ wert: "", titel: "Das ganze Thema" }, ...thema.bereiche.map((b) => ({ wert: b.id, titel: `Bereich ${b.titel}` }))]} />
      <Auswahl wert={wann} symbol="fa-clock" titel="Wann es läuft" onwahl={(w) => (wann = w as "jetzt" | "nachts")}
               optionen={[{ wert: "nachts", titel: "Heute Nacht" }, { wert: "jetzt", titel: "Jetzt" }]} />
      {#if gewaehlt.includes("vertonen")}
        <Auswahl wert={stimme} symbol="fa-microphone" titel="Stimme fürs Vertonen" onwahl={(w) => (stimme = w)}
                 optionen={[{ wert: "", titel: "Stimme wie beim Vorlesen" }, ...stimmen.filter((s) => s.wert)]} />
        <Auswahl wert={format} symbol="fa-file-audio" titel="Format der Hördateien" onwahl={(w) => (format = w as "opus" | "mp3")}
                 optionen={[{ wert: "opus", titel: "Opus (klein)" }, { wert: "mp3", titel: "MP3 (überall)" }]} />
      {/if}
      <button class="knopf primaer" disabled={!gewaehlt.length} onclick={starten}><i class="fa-solid fa-play"></i>Starten</button>
    </div>
  </div>
  {#if stand?.auftraege.length}
    <div class="nacht-laeuft">
      {#each stand.auftraege as a (a.auftrag)}
        <div class="nacht-auftrag">
          <b>{TITEL[a.arbeit]}</b>
          <span>{a.zurueckgestellt || (a.zustand === "fehler" ? `gescheitert: ${a.schritt}` : a.schritt || (a.zustand === "wartet" ? "wartet" : "läuft"))}</span>
          {#if a.anteil !== null && a.zustand === "laeuft"}<span class="spur"><span style="width: {Math.round(a.anteil * 100)}%"></span></span>{/if}
        </div>
      {/each}
    </div>
  {/if}
  {#if stand?.ergebnisse.length}
    <div class="nacht-ergebnisse">
      {#each stand.ergebnisse as e (e.arbeit)}
        <div class="nacht-ergebnis">
          <button class="knopf still" onclick={() => (offenesErgebnis = offenesErgebnis === e.arbeit ? "" : e.arbeit)}>
            <i class="fa-solid {offenesErgebnis === e.arbeit ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>{TITEL[e.arbeit]}</button>
          <span class="ablage" title="liegt {ablageIn()}">{e.ablage}</span>
          {#if offenesErgebnis === e.arbeit}<div class="ergebnis-text">{e.inhalt}</div>{/if}
        </div>
      {/each}
    </div>
  {/if}
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
</details>
