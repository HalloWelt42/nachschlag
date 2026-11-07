<script lang="ts">
  // Reiter Fassungen und Laden der Bibliothek (WIKI-57, Entwurf fassungen.html): Durchsicht des Verzeichnisses, Platz mit
  // Reserve und je Abo drei Plätze (vorige, aktiv, neu) mit Umschalten und Zurück. Was gerade lädt, zeigt seinen
  // Fortschritt nur auf der Seite Aufträge und in der Fußleiste; hier steht der Verweis dorthin.
  import { gehe, seitenFehler } from "appkern-oberflaeche";
  import { datum, zahl } from "../lib/bibliothek.svelte";
  import { groesse, lader, laderLaden, monat } from "../lib/buecherlader.svelte";
  import { abbestellen, durchsichtStarten, umschalten, zurueckSchalten } from "../lib/schnittstelle";
  import Ladebalken from "./Ladebalken.svelte";

  const DURCHSICHT: Record<string, string> = { taeglich: "täglich", woechentlich: "wöchentlich", monatlich: "monatlich" };
  const SPRACHE: Record<string, string> = { de: "Deutsch", en: "Englisch", mul: "Mehrsprachige" };

  const stand = $derived(lader.stand);
  const platz = $derived(stand?.platz ?? null);
  const anteil = (n: number) => (platz && platz.gesamt ? `${(100 * n) / platz.gesamt}%` : "0%");
  const kennung = (k: string) => k.replace(/^.*_(\d{4}-\d{2})$/, "$1");

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
  const wann = (iso: string) => `${datum(iso.slice(0, 10))}, ${iso.slice(11, 16)} Uhr`;
</script>

<div class="katalog-seite bib-oben">
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  {#if stand && !stand.bereit}
    <div class="fundband"><i class="fa-solid fa-circle-info"></i><span>Bücherlader aus: {stand.grund}</span>
      <button class="knopf still" onclick={() => gehe("einstellungen/buecherlader")}>Einstellungen</button></div>
  {/if}

  {#if stand}
    <section class="lade-karte">
      <div class="lade-kopf">
        <h2><i class="fa-solid fa-list-check"></i>Durchsicht</h2>
        <span class="neben">{DURCHSICHT[stand.regeln.durchsicht]}, {stand.regeln.sprachen.map((s) => SPRACHE[s] ?? s).join(", ")}</span>
        <span class="rechts">
          <button class="knopf still" onclick={() => gehe("auftraege")}><i class="fa-solid fa-list-ul"></i>Aufträge</button>
          <button class="knopf" disabled={!stand.bereit || !!arbeitet} onclick={() => tun("durchsicht", durchsichtStarten)}>
            <i class="fa-solid fa-rotate"></i>Jetzt durchsehen</button>
        </span>
      </div>
      {#if stand.letzter_durchgang}
        {@const d = stand.letzter_durchgang}
        <div class="kennzahlen-reihe">
          <div class="kennzahl"><span class="k">Zuletzt</span><span class="w text">{wann(d.begonnen)}</span></div>
          <div class="kennzahl"><span class="k">Nächste</span><span class="w text">{stand.naechster_durchgang ? wann(stand.naechster_durchgang) : "gleich"}</span></div>
          <div class="kennzahl"><span class="k">Bücher</span><span class="w">{zahl(d.buecher)}</span></div>
          <div class="kennzahl"><span class="k">Neu</span><span class="w">{d.erstaufnahme ? "-" : `${d.neue_buecher} / ${d.neue_fassungen}`}</span></div>
        </div>
        {#if !d.erstaufnahme}<div class="unter-zeile">Neu heißt: neue Bücher / neue Fassungen seit der Durchsicht davor.</div>{/if}
        {#each d.hinweise as h}<div class="unter-zeile warn"><i class="fa-solid fa-triangle-exclamation"></i>{h}</div>{/each}
      {:else}
        <div class="unter-zeile">Noch keine Durchsicht.</div>
      {/if}
    </section>
  {/if}

  {#if platz}
    <section class="lade-karte">
      <div class="lade-kopf"><h2><i class="fa-solid fa-hard-drive"></i>Platz</h2>
        <span class="neben"><code>{platz.ordner}</code></span></div>
      <div class="platzbalken">
        <div class="spur" title="belegt durch Bücher, im Laden, sonst belegt, frei">
          <span class="pb-zim" style="width: {anteil(platz.buecher)}"></span>
          <span class="pb-laden" style="width: {anteil(platz.im_laden)}"></span>
          <span class="pb-sonst" style="width: {anteil(Math.max(0, platz.gesamt - platz.frei - platz.buecher - platz.im_laden))}"></span>
          <span class="pb-reserve" style="width: {anteil(Math.min(platz.reserve, platz.frei))}"></span>
        </div>
        <div class="legende">
          <span><i class="fa-solid fa-square pb-zim"></i>Bücher {groesse(platz.buecher)}</span>
          {#if platz.im_laden}<span><i class="fa-solid fa-square pb-laden"></i>im Laden {groesse(platz.im_laden)}</span>{/if}
          <span><i class="fa-solid fa-square pb-sonst"></i>anderes {groesse(Math.max(0, platz.gesamt - platz.frei - platz.buecher - platz.im_laden))}</span>
          <span><i class="fa-solid fa-square pb-reserve"></i>Reserve {groesse(platz.reserve)}, bleibt frei</span>
          <span>frei {groesse(platz.frei)} von {groesse(platz.gesamt)}{platz.hoechstens ? ` · Bücher höchstens ${groesse(platz.hoechstens)}` : ""}</span>
        </div>
      </div>
    </section>
  {/if}

  {#if stand?.bereit}
    <section class="lade-karte">
      <div class="lade-kopf"><h2><i class="fa-solid fa-code-compare"></i>Fassungen je Abo</h2>
        <span class="neben">neue Fassungen {stand.regeln.neue_fassung === "laden" ? "laden von selbst" : "werden nur gemeldet"}{stand.regeln.laden_wann === "nachts" ? ", nur nachts" : ""};
          umschalten nach Bestätigung; die vorige bleibt {stand.regeln.vorige_tage} Tage</span></div>
      {#if !stand.abos.length}
        <div class="unter-zeile">Noch kein Abo. Abonnieren geht im Katalog oder bei Meine Bücher.</div>
      {:else}
        <table class="fassungen-tabelle">
          <thead><tr><th>Buch</th><th>Vorige</th><th>Aktiv</th><th>Neu</th><th></th></tr></thead>
          <tbody>
            {#each stand.abos as a (a.stamm)}
              <tr>
                <td><span class="abo-titel">{a.titel}</span><span class="datei-k">{a.stamm}</span></td>
                <td>
                  {#if a.rueckfall}
                    <div class="platz-f vorige"><span class="f">{monat(kennung(a.rueckfall.kennung))}</span>
                      <span class="z">{a.rueckfall.bleibt ? `Rückfall, bleibt: ${a.rueckfall.bleibt}` : `Rückfall, entfernt ab ${datum(a.rueckfall.entfernt_ab)}`}</span>
                      <button class="knopf still" disabled={!!arbeitet} onclick={() => tun(a.stamm, () => zurueckSchalten(a.stamm))}>
                        <i class="fa-solid fa-rotate-left"></i>Zurück</button></div>
                  {:else}<div class="platz-f ohne"><span class="z">keine</span></div>{/if}
                </td>
                <td>
                  {#if a.lokal_stand}<div class="platz-f aktiv"><span class="f">{monat(a.lokal_stand)}</span><span class="z">aktiv</span></div>
                  {:else}<div class="platz-f ohne"><span class="z">noch nicht da</span></div>{/if}
                </td>
                <td>
                  {#if a.zustand === "laedt"}
                    <div class="platz-f neu"><span class="f">{monat(a.neuester_stand)}</span><span class="z">lädt ({groesse(a.neueste_groesse)})</span>
                      <Ladebalken stamm={a.stamm} /></div>
                  {:else if a.zustand === "wartet_auf_umschalten"}
                    <div class="platz-f neu"><span class="f">{monat(kennung(a.wartet))}</span><span class="z">geladen und geprüft</span>
                      <button class="knopf haupt" disabled={!!arbeitet} onclick={() => tun(a.stamm, () => umschalten(a.stamm))}>
                        <i class="fa-solid fa-right-left"></i>Umschalten</button></div>
                  {:else if a.zustand === "neuer_da" || a.zustand === "nicht_da"}
                    <div class="platz-f neu"><span class="f">{a.neuester_stand ? monat(a.neuester_stand) : "-"}</span>
                      <span class="z">{a.hinweis || (a.neuester_stand ? `im Verzeichnis, ${groesse(a.neueste_groesse)}` : "noch nicht im Verzeichnis gesehen")}</span></div>
                  {:else}<div class="platz-f ohne"><span class="z">{a.neuester_stand ? "nichts Neueres" : "nicht im Verzeichnis"}</span></div>{/if}
                </td>
                <td><button class="knopf still" disabled={!!arbeitet} title="Keine neuen Fassungen mehr laden; das Buch bleibt"
                            onclick={() => tun(a.stamm, () => abbestellen(a.stamm))}><i class="fa-solid fa-bell-slash"></i>Abo beenden</button></td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>
  {/if}

  <div class="unter-zeile">Regeln (Sprachen, wie oft, laden oder melden, wann, Reserve, wie lange die vorige bleibt) stehen unter
    <a href="/einstellungen/buecherlader" onclick={(e) => { e.preventDefault(); gehe("einstellungen/buecherlader"); }}>Einstellungen, Bücherlader</a>.</div>
</div>
