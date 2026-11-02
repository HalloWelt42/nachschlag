<script lang="ts">
  // Ausprobieren (WIKI-48, Entwurf mockups/ausprobieren.html, nur am Rechner): eine Ebene über dem Artikel mit einer
  // Kopie des Beispiels. Links der Editor der Codeschmiede (Haltepunkte in der Rinne), rechts Ausgabe und Debugger.
  // Gerechnet wird in der Sandbox der Codeschmiede; der Lauf ist aufgezeichnet, darum geht jeder Schritt vor und zurück.
  // Das Original im Artikel bleibt; "Zurücksetzen" holt es wieder, "Behalten" legt die Kopie als eigenes Beispiel unter
  // den Code, aus dem sie stammt. Escape oder Schließen kehren zurück, die Stelle im Artikel bleibt.
  import { onMount, untrack } from "svelte";
  import { DebuggerBereich, DebugSitzung, EditorBereich } from "appkern-oberflaeche/code";
  import { ausprobierstand, beispielAendern, beispielAnlegen, DATEINAMEN, probelauf, SPRACHNAMEN, SYMBOLE, type Ausprobierstand,
           type Beispiel, type Probe } from "../lib/ausprobieren";

  let { probe, onzu, onbehalten }: {
    probe: Probe;
    onzu: () => void;
    /** ein eigenes Beispiel wurde angelegt oder geändert */
    onbehalten: (beispiel: Beispiel) => void;
  } = $props();

  // die Ebene arbeitet an einer Kopie: was sie beim Öffnen bekommt, ist das Original
  const { code: original, sprache, eigen: geoeffnet } = untrack(() => probe);
  let code = $state(original);
  let eigen = $state.raw<Beispiel | null>(geoeffnet);
  let gesichert = $state(original);                 // Stand des eigenen Beispiels (Behalten ändert es danach)
  let reiter = $state<"ausgabe" | "debugger">("ausgabe");
  let zeile = $state<number | null>(null);
  let stand = $state.raw<Ausprobierstand | null>(null);
  let behalten = $state<{ titel: string } | null>(null);
  let speichert = $state(false);
  let meldung = $state("");
  const sitzung = new DebugSitzung();

  const kann = $derived(!!stand?.bereit && stand.sprachen.includes(sprache));
  const lage = $derived(!stand ? "Frage die Sandbox ..." : kann ? "Sandbox bereit, ohne Netz"
    : stand.bereit ? `${SPRACHNAMEN[sprache]} läuft in der Sandbox noch nicht` : stand.grund);
  const lauf = $derived(sitzung.lauf);

  onMount(() => {
    void ausprobierstand().then((s) => (stand = s));
  });

  function starten(ziel: "ausgabe" | "debugger") {
    if (!kann || sitzung.laeuft) return;
    reiter = ziel;
    void sitzung.starten(code, probelauf(sprache));
  }

  function zuruecksetzen() {
    code = original;
    sitzung.beenden();
  }

  function behaltenOeffnen() {
    meldung = "";
    behalten = { titel: eigen ? eigen.titel : `Abwandlung von ${probe.titel}` };
  }

  async function speichern(e: SubmitEvent) {
    e.preventDefault();
    const titel = behalten?.titel.trim() ?? "";
    if (!titel || speichert) return;
    speichert = true;
    meldung = "";
    try {
      const b = eigen ? await beispielAendern(eigen.id, titel, code)
        : await beispielAnlegen({ buch: probe.buch, pfad: probe.pfad, titel, sprache, code, vorlage: probe.titel, block: probe.block });
      eigen = b;
      gesichert = code;
      behalten = null;
      meldung = `Behalten als "${b.titel}" unter dem Beispiel im Artikel`;
      onbehalten(b);
    } catch (f) {
      meldung = f instanceof Error ? f.message : String(f);
    } finally {
      speichert = false;
    }
  }

  function taste(e: KeyboardEvent) {
    if (e.defaultPrevented) return;                  // der Editor hat sie selbst gebraucht (etwa die Vervollständigung)
    if (e.key === "Escape") {
      e.preventDefault();
      if (behalten) behalten = null;
      else onzu();
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      starten("ausgabe");
    }
  }
</script>

<svelte:window onkeydown={taste} />

<div class="probe-schleier" onclick={onzu} aria-hidden="true"></div>
<div class="probe" role="dialog" aria-modal="true" aria-label="Ausprobieren">
  <header class="probe-kopf">
    <i class="fa-solid fa-flask" aria-hidden="true"></i>
    <div class="probe-titel"><b>Ausprobieren</b><span>{eigen ? `Dein Beispiel: ${eigen.titel}` : probe.titel} · {probe.quelle}</span></div>
    <span class="chip"><i class={SYMBOLE[sprache]} aria-hidden="true"></i>{SPRACHNAMEN[sprache]}</span>
    <span class="probe-lage" class:aus={!!stand && !kann}><span class="punkt"></span>{lage}</span>
    <div class="rechts">
      <button class="knopf primaer" onclick={() => starten("ausgabe")} disabled={!kann || sitzung.laeuft}
              title="In der Sandbox ausführen (Strg Enter)"><i class="fa-solid fa-play" aria-hidden="true"></i>Ausführen<kbd>Strg Enter</kbd></button>
      <button class="knopf" class:an={reiter === "debugger" && sitzung.aktiv} onclick={() => starten("debugger")}
              disabled={!kann || sitzung.laeuft} title="Den Lauf aufzeichnen und Schritt für Schritt ansehen"><i class="fa-solid fa-bug" aria-hidden="true"></i>Debuggen</button>
      <button class="knopf still" onclick={zuruecksetzen} disabled={code === original}
              title={geoeffnet ? "Wieder dein Beispiel, wie es gespeichert war" : "Wieder das Beispiel aus dem Artikel"}><i class="fa-solid fa-rotate-left" aria-hidden="true"></i>Zurücksetzen</button>
      <button class="knopf still" class:an={!!behalten} onclick={behaltenOeffnen}
              title={eigen ? "Dein Beispiel mit diesem Code speichern" : "Als dein Beispiel unter dem Artikel behalten"}><i class="fa-solid fa-user-pen" aria-hidden="true"></i>Behalten</button>
      <button class="rund" onclick={onzu} title="Schließen (Esc)" aria-label="Schließen"><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>
    </div>
  </header>

  {#if behalten}
    <form class="probe-leiste" onsubmit={speichern}>
      <i class="fa-solid fa-user-pen" aria-hidden="true"></i>
      <label for="probe-name">Name deines Beispiels</label>
      <!-- svelte-ignore a11y_autofocus -->
      <input id="probe-name" class="eingabe" bind:value={behalten.titel} maxlength="200" autofocus />
      <button class="knopf primaer" type="submit" disabled={!behalten.titel.trim() || speichert}>{eigen ? "Speichern" : "Behalten"}</button>
      <button class="knopf still" type="button" onclick={() => (behalten = null)}>Abbrechen</button>
      {#if meldung}<span class="fehler">{meldung}</span>{/if}
    </form>
  {:else if meldung}
    <div class="probe-leiste gut"><i class="fa-solid fa-check" aria-hidden="true"></i>{meldung}</div>
  {/if}

  <div class="probe-flaeche">
    <div class="probe-editor">
      <div class="probe-reiter">
        <span class="aktiv"><i class={SYMBOLE[sprache]} aria-hidden="true"></i>{DATEINAMEN[sprache]}</span>
        {#if code !== gesichert}<span class="geaendert">geändert</span>{/if}
      </div>
      <div class="probe-code">
        <EditorBereich {sprache} bind:code markierteZeile={reiter === "debugger" ? zeile : null} mitHaltepunkten
                       bind:haltepunkte={sitzung.haltepunkte} />
      </div>
      <div class="probe-hinweis"><i class="fa-solid fa-circle" aria-hidden="true"></i>Haltepunkt: links neben die Zeilennummer klicken</div>
    </div>

    <aside class="probe-rechts">
      <div class="probe-reiterleiste" role="tablist">
        <button role="tab" aria-selected={reiter === "ausgabe"} class:aktiv={reiter === "ausgabe"} onclick={() => (reiter = "ausgabe")}>Ausgabe</button>
        <button role="tab" aria-selected={reiter === "debugger"} class:aktiv={reiter === "debugger"} onclick={() => (reiter = "debugger")}>Debugger</button>
      </div>

      {#if reiter === "ausgabe"}
        {#if sitzung.laeuft}
          <p class="leise"><i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Läuft in der Sandbox ...</p>
        {:else if sitzung.fehler}
          <div class="probe-meldung"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i><span>{sitzung.fehler}</span></div>
        {:else if lauf}
          {#if sitzung.veraltet(code)}<p class="leise"><i class="fa-solid fa-pen" aria-hidden="true"></i> Code geändert: Ausführen zeigt den neuen Stand.</p>{/if}
          <pre class="probe-ausgabe">{#if lauf.ausgabe}{lauf.ausgabe}{:else}<span class="leer">Keine Ausgabe</span>{/if}</pre>
          {#if lauf.fehler}
            <div class="probe-meldung"><i class="fa-solid fa-bug" aria-hidden="true"></i><span>{lauf.fehler}{lauf.fehlerzeile ? ` (Zeile ${lauf.fehlerzeile})` : ""}</span></div>
          {/if}
          {#if lauf.zeitueberschreitung}<p class="leise">Zeit überschritten: der Lauf wurde abgebrochen.</p>{/if}
          <p class="leise">Lief <span class="zahl">{Math.round(lauf.laufzeit_ms)}</span> ms in der Sandbox der Codeschmiede.</p>
        {:else}
          <p class="leise">Ausführen schickt den Code in die Sandbox der Codeschmiede: ohne Netz, mit Grenzen für Zeit und Speicher.</p>
        {/if}
      {:else}
        {#if !sitzung.aktiv}
          <p class="leise">Debuggen zeichnet den Lauf auf: danach geht jeder Schritt vor und zurück, mit Aufrufstapel, Speicher und Ausgabe bis dahin.</p>
        {/if}
        <DebuggerBereich {sitzung} {sprache} {code} bind:zeile />
      {/if}
      <div class="probe-fuss"><i class="fa-solid fa-circle-info" aria-hidden="true"></i>Du arbeitest an einer Kopie; das Beispiel im Artikel bleibt, wie es ist.</div>
    </aside>
  </div>
</div>

<style>
  .probe-schleier { position: fixed; inset: 0; z-index: 50; background: var(--schleier); }
  .probe { position: fixed; z-index: 51; inset: 56px 40px 40px 40px; display: flex; flex-direction: column;
           background: var(--flaeche); border-radius: var(--r3); box-shadow: var(--schatten-schwebend), 0 0 0 1px var(--rand); overflow: hidden;
           --schrift-code: var(--schrift-editor); font-variant-ligatures: none; }
  .probe-kopf { display: flex; flex-wrap: wrap; align-items: center; gap: var(--a2) var(--a3); padding: 10px 14px; background: var(--flaeche-2); }
  .probe-kopf > i { color: var(--petrol); font-size: var(--gross); }
  .probe-titel { display: flex; flex-direction: column; line-height: 1.2; min-width: 0; }
  .probe-titel span { font-size: var(--klein); color: var(--text-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip { display: inline-flex; align-items: center; gap: 6px; }
  .probe-lage { display: inline-flex; align-items: center; gap: 6px; font-size: var(--klein); color: var(--text-2); }
  .probe-lage .punkt { width: 8px; height: 8px; border-radius: 50%; background: var(--gut); flex: none; }
  .probe-lage.aus .punkt { background: var(--warn); }
  .rechts { margin-left: auto; display: flex; gap: 6px; align-items: center; }
  .rechts .knopf { gap: 6px; }
  kbd { margin-left: 4px; font-family: var(--schrift-zahl); font-size: var(--marke); opacity: .75; }

  .probe-leiste { display: flex; flex-wrap: wrap; align-items: center; gap: var(--a2) var(--a3); padding: 8px 14px; font-size: var(--klein);
                  background: color-mix(in srgb, var(--petrol) 8%, var(--flaeche)); box-shadow: inset 0 -1px 0 var(--rand); }
  .probe-leiste > i { color: var(--petrol); }
  .probe-leiste.gut > i { color: var(--gut); }
  .probe-leiste input { flex: 1 1 260px; max-width: 480px; }
  .probe-leiste .fehler { color: var(--gefahr); }

  .probe-flaeche { flex: 1; display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); min-height: 0; }
  .probe-editor { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; min-height: 0; background: var(--ed-grund); }
  .probe-reiter { display: flex; align-items: center; gap: var(--a3); padding: 6px 12px; font-size: var(--klein); color: var(--ed-nr); background: var(--ed-rand); }
  .probe-reiter .aktiv { color: var(--ed-text); display: inline-flex; gap: 6px; align-items: center; font-family: var(--schrift-editor); }
  .probe-reiter .geaendert { margin-left: auto; color: var(--warn); }
  .probe-code { min-height: 0; overflow: hidden; }
  .probe-hinweis { padding: 8px 12px; font-size: var(--klein); color: var(--ed-nr); background: var(--ed-rand); display: flex; gap: 8px; align-items: center; }
  .probe-hinweis i { color: var(--ed-haltepunkt); font-size: var(--marke); }

  .probe-rechts { display: flex; flex-direction: column; gap: var(--a3); padding: var(--a3) var(--a4); overflow-y: auto; min-height: 0; }
  .probe-reiterleiste { display: flex; gap: 4px; flex: none; }
  .probe-reiterleiste button { border: 0; background: transparent; font: inherit; padding: 6px 12px; border-radius: var(--r2); color: var(--text-2); cursor: pointer; }
  .probe-reiterleiste button.aktiv { background: var(--flaeche-2); color: var(--text); font-weight: 600; }
  .leise { margin: 0; font-size: var(--klein); color: var(--text-2); }
  .zahl { font-family: var(--schrift-zahl); font-variant-numeric: tabular-nums; }
  .probe-ausgabe { margin: 0; padding: 10px 12px; border-radius: var(--r2); background: var(--ed-konsole); color: var(--ed-konsole-text);
                   font-family: var(--schrift-editor); font-size: var(--klein); white-space: pre-wrap; overflow-wrap: anywhere; flex: none; }
  .probe-ausgabe .leer { opacity: .6; font-style: italic; }
  .probe-meldung { display: flex; gap: var(--a2); align-items: baseline; padding: 8px 10px; border-radius: var(--r2); font-size: var(--klein);
                   background: color-mix(in srgb, var(--gefahr) 10%, transparent); color: var(--text); }
  .probe-meldung i { color: var(--gefahr); }
  .probe-fuss { margin-top: auto; padding-top: var(--a3); font-size: var(--klein); color: var(--text-3); display: flex; gap: 8px; align-items: baseline; }
</style>
