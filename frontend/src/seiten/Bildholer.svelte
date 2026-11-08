<script lang="ts">
  // Einstellungen, Reiter Bildholer (WIKI-80, Entwurf mockups/einstellungen-bilder.html): der Stand des Bildholers
  // (eigenes Programm im eigenen Container) mit Zahlen, Vorgemerktem je Stufe und den zuletzt geholten Bildern; anhalten
  // und fortsetzen. Die Regeln stehen im Reiter Bilder. Der Stand frischt sich alle paar Sekunden auf, solange er offen ist.
  import { seitenFehler } from "appkern-oberflaeche";
  import { onDestroy } from "svelte";
  import { bildholerAnhalten, bildholerStand, type Bildholerstand } from "../lib/schnittstelle";

  const TAKT_MS = 5000;
  const ZUSTAND: Record<Bildholerstand["zustand"], { text: string; symbol: string; art: string }> = {
    laeuft: { text: "läuft", symbol: "fa-circle-play", art: "gut" },
    wartet: { text: "wartet", symbol: "fa-hourglass-half", art: "" },
    ruht: { text: "ruht", symbol: "fa-moon", art: "" },
    angehalten: { text: "angehalten", symbol: "fa-circle-pause", art: "warn" },
    voll: { text: "Platz voll", symbol: "fa-hard-drive", art: "warn" },
    aus: { text: "aus", symbol: "fa-power-off", art: "" },
  };
  const STUFEN = [{ k: "0", name: "Gerade geöffnet" }, { k: "1", name: "Gelesen, gemerkt, in Themen" }];

  let stand = $state<Bildholerstand | null>(null);
  let fehler = $state("");
  let laeuft = $state(false);
  async function laden() {
    try {
      stand = await bildholerStand();
      fehler = "";
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }
  void laden();
  const uhr = setInterval(() => void laden(), TAKT_MS);
  onDestroy(() => clearInterval(uhr));

  async function umschalten() {
    if (!stand || laeuft) return;
    laeuft = true;
    try {
      stand = await bildholerAnhalten(stand.zustand !== "angehalten");
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      laeuft = false;
    }
  }
  const zahl = (n: number) => n.toLocaleString("de-DE");
  const gb = (b: number) => (b / 1e9).toLocaleString("de-DE", { maximumFractionDigits: 1 });
  const z = $derived(stand ? ZUSTAND[stand.zustand] : null);
</script>

<div class="bh-seite">
  {#if fehler && !stand}
    <p class="bh-hinweis"><i class="fa-solid fa-plug-circle-xmark"></i>{fehler}</p>
  {:else if stand && z}
    <section class="karte bh-lage">
      <div class="bh-kopf">
        <b>Große Bilder</b>
        <span class="bh-zustand {z.art}"><i class="fa-solid {z.symbol}"></i>{z.text}{stand.zustand === "laeuft" ? `, ein Bild alle ${zahl(stand.abstand_s)} s` : ""}</span>
        <button class="knopf bh-knopf" onclick={umschalten} disabled={laeuft || stand.zustand === "aus"}>
          <i class="fa-solid {stand.zustand === 'angehalten' ? 'fa-play' : 'fa-pause'}"></i>{stand.zustand === "angehalten" ? "Fortsetzen" : "Anhalten"}</button>
      </div>
      {#if stand.grund}<p class="bh-grund">{stand.grund}</p>{/if}
      <div class="bh-zahlen">
        <div><span class="k">Geladen</span><span class="w">{zahl(stand.geladen)}</span></div>
        <div><span class="k">Heute</span><span class="w">{zahl(stand.heute)}</span></div>
        <div><span class="k">Belegt</span><span class="w">{gb(stand.belegt_bytes)} GB</span><span class="u">von {gb(stand.platz_bytes)} GB</span></div>
        <div><span class="k">Nicht in der Quelle</span><span class="w">{zahl(stand.fehlgeschlagen)}</span></div>
      </div>
      <div class="bh-stufen">
        {#each STUFEN as s (s.k)}
          <div class="bh-stufe"><i class="fa-solid {stand.offen[s.k] ? 'fa-circle-play' : 'fa-circle-check'}"></i><span>{s.name}</span>
            <span class="zahl">{stand.offen[s.k] ? `${zahl(stand.offen[s.k])} vorgemerkt` : "nichts offen"}</span></div>
        {/each}
      </div>
      {#if stand.zuletzt.length}
        <div class="bh-zuletzt"><span class="k">Zuletzt</span>
          {#each stand.zuletzt as b (b.quelle + b.name)}
            <span class="bh-bild" title={b.name}>{b.name.replace(/_/g, " ")}<span class="bh-px">{zahl(b.breite)} px</span></span>
          {/each}
        </div>
      {/if}
    </section>
    <p class="bh-hinweis"><i class="fa-solid fa-circle-info"></i>Der Bildholer ist ein eigenes Programm im eigenen Container neben Nachschlag; Nachschlag liest nur seine Ablage. Die Regeln stehen im Reiter Bilder.</p>
  {/if}
</div>
