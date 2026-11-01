<script lang="ts" module>
  import { aufnahmeEinrichten, aufnehmen, hole } from "appkern-oberflaeche";

  /** Ob die Spracheingabe geht (Leitstelle, Hördienst freigegeben); einmal je Sitzung gefragt, nach Minuten neu. */
  const NEU_FRAGEN_MS = 5 * 60_000;
  let stand: Promise<boolean> | null = null;
  let gefragt = 0;
  function bereit(): Promise<boolean> {
    if (!stand || Date.now() - gefragt > NEU_FRAGEN_MS) {
      gefragt = Date.now();
      stand = hole<{ bereit: boolean }>("/sprache").then((s) => s.bereit, () => false);
    }
    return stand;
  }

  /** Im Tippen starten (Safari am iPhone hält den Ton sonst an): die Stücke gehen an den Hördienst von Nachschlag. */
  function starten(): void {
    aufnahmeEinrichten({ app: "nachschlag", hoeren: "/sprache", name: "Spracheingabe" });
    void aufnehmen();
  }
</script>

<script lang="ts">
  // Spracheingabe (WIKI-42, docs/SUCHE.md Punkt 8): Tippen startet, Tippen oder drei Sekunden Stille beenden. Der Text
  // wächst beim Sprechen (Live-Mitschrift des Appkerns über den Hördienst der Leitstelle) und geht laufend an `live`,
  // am Ende an `fertig`; die Aufnahme selbst wird verworfen. Derselbe Baustein für Suchfeld und Notizen. Ohne
  // Hördienst erscheint kein Knopf (nur zeigen, was geht).
  import { aufnahme, aufnahmeAbbrechen, aufnahmeBeenden, aufnahmeVerwerfen, mitschriftAbwarten } from "appkern-oberflaeche";
  import { onDestroy, onMount } from "svelte";

  let { live, fertig, titel = "Sprechen" }: { live?: (text: string) => void; fertig: (text: string) => void; titel?: string } = $props();

  let da = $state(false);
  let meins = $state(false);            // die laufende Aufnahme gehört diesem Knopf
  let umsetzen = $state(false);
  const text = $derived(aufnahme.mitschrift.map((s) => s.text).join(" ").trim());
  const hoert = $derived(meins && aufnahme.laeuft);

  onMount(() => void bereit().then((b) => (da = b)));
  onDestroy(() => {
    if (meins && aufnahme.laeuft) void aufnahmeAbbrechen();
  });

  $effect(() => {
    if (meins && text) live?.(text);
  });
  // Stille beendet, sobald schon etwas gesagt wurde
  $effect(() => {
    if (hoert && aufnahme.signal === "still" && text && !umsetzen) void stopp();
  });

  async function stopp() {
    umsetzen = true;
    const datei = await aufnahmeBeenden("Spracheingabe");
    await mitschriftAbwarten();
    if (datei) await aufnahmeVerwerfen(datei.info.id);
    const ergebnis = aufnahme.mitschrift.map((s) => s.text).join(" ").trim();
    meins = false;
    umsetzen = false;
    if (ergebnis) fertig(ergebnis);
  }

  function tippen() {
    if (hoert) {
      if (!umsetzen) void stopp();
      return;
    }
    meins = true;
    starten();
  }
</script>

{#if da}
  <button type="button" class="sprechknopf" class:hoert title={hoert ? "Fertig gesprochen" : titel} aria-label={hoert ? "Fertig gesprochen" : titel}
          onmousedown={(e) => e.preventDefault()} onclick={tippen}>
    <i class="fa-solid {umsetzen ? 'fa-spinner fa-spin' : hoert ? 'fa-stop' : 'fa-microphone'}"></i>
  </button>
  {#if meins && aufnahme.fehler}<span class="sprech-stand">{aufnahme.fehler}</span>{/if}
{/if}
