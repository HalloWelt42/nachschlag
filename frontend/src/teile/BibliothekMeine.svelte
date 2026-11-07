<script lang="ts">
  // Reiter Meine Bücher der Bibliothek (WIKI-57): jede Quelle mit Kennzahlen, Fähigkeiten und Abo. Hat eine Art von Buch
  // noch keinen eigenen Baustein, steht das sichtbar daran ("Eigene Ansicht fehlt", mit dem Erzeuger), und oben fasst ein
  // Band zusammen, für welche Erzeuger eine Ansicht fehlt: so sieht man, wo noch gebaut werden muss.
  import { gehe, seitenFehler } from "appkern-oberflaeche";
  import { bibliothek, datum, zahl } from "../lib/bibliothek.svelte";
  import { groesse, lader, laderLaden, monat, ZUSTAND } from "../lib/buecherlader.svelte";
  import { abbestellen, abonnieren, bestandAbonnieren } from "../lib/schnittstelle";
  import type { Art, Buch } from "../lib/typen";
  import { lesen } from "../lib/ziele";
  import Sprachmarke from "./Sprachmarke.svelte";

  const SYMBOL: Record<Art, string> = { enzyklopaedie: "fa-book", dokumentation: "fa-code", frage_antwort: "fa-comments",
                                       webseite: "fa-globe", sonstiges: "fa-box-archive" };
  const ART: Record<Art, string> = { enzyklopaedie: "Nachschlagewerk", dokumentation: "Dokumentation", frage_antwort: "Frage und Antwort",
                                    webseite: "Webseite", sonstiges: "unbekannte Art" };

  /** Stamm einer Datei (Kennung ohne Stand), wie ihn der Bücherlader für Abos führt. */
  const stamm = (b: Buch) => b.kennung.replace(/_\d{4}-\d{2}$/, "");
  const abos = $derived(new Map((lader.stand?.abos ?? []).map((a) => [a.stamm, a])));
  const buecher = $derived([...bibliothek.buecher].sort((a, b) => Number(!!a.archiv) - Number(!!b.archiv)));
  const ohneAnsicht = $derived.by(() => {
    const je = new Map<string, Buch[]>();
    for (const b of bibliothek.buecher.filter((x) => !x.faehigkeiten.lesedesign && !x.archiv)) {
      const e = b.erzeuger.split(/[ ,]/)[0] || "unbekannt";
      je.set(e, [...(je.get(e) ?? []), b]);
    }
    return [...je.entries()];
  });
  const offen = $derived(lader.stand?.bereit ? bibliothek.buecher.filter((b) => !b.archiv && !abos.has(stamm(b))).length : 0);

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
</script>

<div class="bibliothek">
  <div class="ordnerzeile">
    <i class="fa-solid fa-folder-open"></i>
    <span>Bücher aus <code>{lader.stand?.platz?.ordner ?? "dem Ordner der Bibliothek"}</code>; neue Dateien erscheinen von selbst.</span>
    <span class="rechts">
      {#if lader.stand?.platz}<span>belegt <b class="zahl">{groesse(lader.stand.platz.buecher)}</b> · frei <b class="zahl">{groesse(lader.stand.platz.frei)}</b></span>{/if}
      {#if offen}<button class="knopf" disabled={!!arbeitet} onclick={() => tun("bestand", bestandAbonnieren)}
                         title="Jedes Buch hier abonnieren; neuere Fassungen laden dann von selbst">
        <i class="fa-solid fa-bell"></i>Alle {offen} abonnieren</button>{/if}
    </span>
  </div>
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  {#if lader.stand && !lader.stand.bereit}
    <div class="fundband"><i class="fa-solid fa-circle-info"></i><span>Bücherlader aus: {lader.stand.grund}</span>
      <button class="knopf still" onclick={() => gehe("einstellungen/buecherlader")}>Einstellungen</button></div>
  {/if}
  {#if ohneAnsicht.length}
    <div class="fundband ansicht-fehlt"><i class="fa-solid fa-person-digging"></i>
      <span>Eigene Ansicht fehlt für {ohneAnsicht.reduce((s, [, l]) => s + l.length, 0)} {ohneAnsicht.reduce((s, [, l]) => s + l.length, 0) === 1 ? "Buch" : "Bücher"},
        sie öffnen in der Originalansicht: {ohneAnsicht.map(([e, l]) => `${e} (${l.map((b) => b.titel).join(", ")})`).join("; ")}</span></div>
  {/if}

  {#each buecher as b (b.kennung)}
    {@const abo = abos.get(stamm(b))}
    <div class="buch-gross" class:archiviert={!!b.archiv}>
      <span class="sym"><i class="fa-solid {SYMBOL[b.art]}"></i></span>
      <div class="kopfzeile"><b>{b.titel}</b><Sprachmarke kuerzel={b.sprache} name /><span class="datei">{b.kennung}.zim</span></div>
      <div class="aktionen">
        <button class="knopf" onclick={() => lesen(b.kennung, b.startseite)}><i class="fa-solid fa-book-open"></i>Öffnen</button>
        {#if lader.stand?.bereit && !b.archiv}
          {#if abo}
            <button class="knopf still" disabled={!!arbeitet} title="Keine neuen Fassungen mehr laden; das Buch bleibt"
                    onclick={() => tun(b.kennung, () => abbestellen(abo.stamm))}><i class="fa-solid fa-bell-slash"></i>Abo beenden</button>
          {:else}
            <button class="knopf" disabled={!!arbeitet} title="Neuere Fassungen von selbst laden"
                    onclick={() => tun(b.kennung, () => abonnieren(stamm(b)))}><i class="fa-solid fa-bell"></i>Abonnieren</button>
          {/if}
        {/if}
      </div>
      <div class="beschr">{b.beschreibung || ART[b.art]} · Stand {datum(b.stand)} · {ART[b.art]}
        {#if b.archiv} · im Archiv{b.archiv.grund === "ersetzt" ? ", ersetzt durch eine neuere Fassung" : ""}{/if}</div>
      <div class="kennzahlen">
        <div class="kennzahl"><span class="k">Artikel</span><span class="w">{zahl(b.artikel)}</span></div>
        <div class="kennzahl"><span class="k">Einträge</span><span class="w">{zahl(b.eintraege)}</span></div>
        <div class="kennzahl"><span class="k">Medien</span><span class="w">{zahl(b.medien)}</span></div>
        <div class="kennzahl"><span class="k">Größe</span><span class="w">{groesse(b.groesse)}</span></div>
        <div class="kennzahl"><span class="k">Abo</span>
          <span class="w text">{#if abo}{ZUSTAND[abo.zustand].text}{#if abo.zustand === "neuer_da"} ({monat(abo.neuester_stand)}){/if}{:else}kein Abo{/if}</span></div>
      </div>
      <div class="faehig">
        {#if b.faehigkeiten.lesedesign}<span class="faehigkeit an"><i class="fa-solid fa-book-open-reader"></i>Eigene Ansicht</span>
        {:else}<span class="faehigkeit fehlt" title="Für diese Art von Buch gibt es noch keinen Baustein; es öffnet in der Originalansicht">
          <i class="fa-solid fa-person-digging"></i>Eigene Ansicht fehlt, Originalansicht</span>{/if}
        {#if b.faehigkeiten.volltext}<span class="faehigkeit an"><i class="fa-solid fa-magnifying-glass"></i>Volltextindex</span>{/if}
        {#if b.faehigkeiten.titelindex}<span class="faehigkeit an"><i class="fa-solid fa-heading"></i>Titelindex</span>{/if}
        {#if b.faehigkeiten.bilder}<span class="faehigkeit an"><i class="fa-solid fa-image"></i>Bilder</span>{/if}
        <span class="faehigkeit"><i class="fa-solid fa-gears"></i>Erzeuger {b.erzeuger || "unbekannt"}</span>
      </div>
    </div>
  {/each}
  {#each bibliothek.fehler as f}<div class="fehlertext">{f}</div>{/each}
</div>
