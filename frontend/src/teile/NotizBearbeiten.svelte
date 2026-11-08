<script lang="ts">
  // Eine Notiz bearbeiten (Entwurf mockups/notizen.html, rechte Leiste; am Telefon im Blatt): Stelle, Text, speichert
  // von selbst. Eine neue Notiz am ganzen Artikel kommt als `entwurf` und entsteht erst mit dem ersten Text; eine Notiz
  // an einer Stelle gibt es schon (als Markierung), sobald die Stelle markiert ist. Bilder (WIKI-51) kommen aus der
  // Zwischenablage (Einfügen im Textfeld), durch Ablegen oder aus einer Datei; sie liegen in der Kellerwolke und
  // stehen unter dem Text, groß im Leuchtkasten. Ein Bild an einem Entwurf legt die Notiz an.
  import { onDestroy, untrack } from "svelte";
  import { kopieren, seitenFehler } from "appkern-oberflaeche";
  import { Auswahl } from "appkern-oberflaeche";
  import { buchName } from "../lib/bibliothek.svelte";
  import { ZITIERFORMEN, zitierform, zitierformMerken } from "../lib/recherche.svelte";
  import { zitateHolen, type Zitate } from "../lib/schnittstelle";
  import { RUECKMELDUNG_MS, zitatMitHerkunft } from "../lib/zitat";
  import Sprechknopf from "./Sprechknopf.svelte";
  import Leuchtkasten from "./Leuchtkasten.svelte";
  import type { Medium } from "../lib/medien";
  import { bilderAus, meins, notieren, notizAendern, notizBildAdresse, notizBildAnfuegen, notizBildEntfernen, notizLoeschen,
           type Notiz, type NotizNeu } from "../lib/meins.svelte";

  const SPEICHERN_NACH_MS = 700;
  const ZEIT_TAKT_MS = 5000;
  const NACHFRAGE_MS = 4000;          // so lange fragt das Entfernen eines Bilds nach

  let { notiz = null, entwurf = null, zurStelle, onweg }: {
    notiz?: Notiz | null;
    entwurf?: NotizNeu | null;
    zurStelle?: () => void;
    onweg?: () => void;          // gelöscht
  } = $props();

  let text = $state("");
  let id = $state("");
  let gespeichertUm = $state(0);
  let jetzt = $state(Date.now());
  let speichert = $state(false);
  let fehler = $state("");
  let loeschenFragen = $state(false);
  let kopiert = $state<"" | "ja" | "nein">("");
  let warten: ReturnType<typeof setTimeout> | undefined;
  let laufend: Promise<void> = Promise.resolve();      // das Speichern, das gerade unterwegs ist
  let weg = false;                                       // gelöscht: nichts mehr speichern
  let feld = $state<HTMLTextAreaElement>();
  const feldId = $props.id();
  let dateiwahl = $state<HTMLInputElement>();
  let laedtHoch = $state(0);                            // so viele Bilder sind unterwegs
  let gross = $state<number | null>(null);              // Bild im Leuchtkasten
  let entfernenFragen = $state<string | null>(null);   // Bild, dessen Entfernen gerade nachfragt
  let nachfrage: ReturnType<typeof setTimeout> | undefined;

  // Eine andere Notiz gewählt (dieselbe kommt nach dem Speichern als neues Objekt, darum zählt ihre Kennung; ein
  // Entwurf zählt als er selbst): was noch aussteht, zuerst für die bisherige speichern
  let schluessel: unknown = undefined;
  $effect.pre(() => {
    const k = notiz ? notiz.id : entwurf;
    untrack(() => {
      if (k === schluessel) return;
      schluessel = k;
      void jetztSpeichern();
      id = notiz?.id ?? "";
      text = notiz?.text ?? entwurf?.text ?? "";
      gespeichertUm = 0;
      loeschenFragen = false;
      fehler = "";
    });
  });

  const takt = setInterval(() => (jetzt = Date.now()), ZEIT_TAKT_MS);
  onDestroy(() => {
    clearInterval(takt);
    void jetztSpeichern();
  });

  const zitat = $derived(notiz?.zitat ?? entwurf?.zitat ?? "");
  const titel = $derived(notiz?.titel ?? entwurf?.titel ?? "");
  const abschnitt = $derived(notiz?.abschnitt ?? entwurf?.abschnitt ?? "");
  const belege = $derived(notiz?.belege ?? entwurf?.belege ?? []);
  const quelleUrl = $derived(notiz?.quelle_url ?? entwurf?.quelle_url ?? "");
  // die Bilder aus dem Stand von Meins (ändert sich mit jedem Hochladen und Entfernen), sonst die der gezeigten Notiz
  const bilder = $derived(meins.notizen.find((n) => n.id === id)?.bilder ?? (notiz?.id === id ? notiz?.bilder : null) ?? []);
  const medien = $derived<Medium[]>(bilder.map((b) => ({
    buch: notiz?.buch ?? entwurf?.buch ?? "", pfad: notiz?.pfad ?? entwurf?.pfad ?? "", artikel: titel, abschnitt,
    bild: notizBildAdresse(id, b.id), breite: 0, hoehe: 0, unterschrift: b.name, datei: b.name })));

  /** Bilder an die Notiz; einen Entwurf legt das erste Bild an (mit dem Text, der schon da ist). */
  async function bilderAnfuegen(dateien: File[]) {
    if (!dateien.length) return;
    fehler = "";
    laedtHoch += dateien.length;
    try {
      await jetztSpeichern();
      if (!id && entwurf) id = (await notieren({ ...entwurf, text })).id;
      if (!id) return;
      for (const d of dateien) {
        await notizBildAnfuegen(id, d);
        laedtHoch -= 1;
      }
      gespeichertUm = Date.now();
      jetzt = gespeichertUm;
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      laedtHoch = 0;
    }
  }

  function einfuegen(e: ClipboardEvent) {
    const neu = bilderAus(e.clipboardData);
    if (!neu.length) return;                            // Text fügt das Feld selbst ein
    e.preventDefault();
    void bilderAnfuegen(neu);
  }

  /** Entfernen in zwei Klicks: der erste fragt am Bild nach, der zweite entfernt */
  async function bildEntfernen(bild: string) {
    if (entfernenFragen !== bild) {
      entfernenFragen = bild;
      clearTimeout(nachfrage);
      nachfrage = setTimeout(() => (entfernenFragen = null), NACHFRAGE_MS);
      return;
    }
    entfernenFragen = null;
    try {
      await notizBildEntfernen(id, bild);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }
  // Zitiervorschlag (WIKI-31) in der Form, die dieses Gerät gewählt hat. Alle Formen kommen vorab vom Server (dort
  // stehen sie an einer Stelle, mit Autor und Datum bei Frage und Antwort); die Zwischenablage gibt es nur im Klick.
  let zitate = $state.raw<Zitate | null>(null);
  let zitatKopiert = $state<"" | "ja" | "nein">("");
  $effect(() => {
    const b = notiz?.buch ?? entwurf?.buch ?? "", p = notiz?.pfad ?? entwurf?.pfad ?? "";
    zitate = null;
    if (!quelleUrl || !b || !p) return;
    const abruf = new AbortController();
    zitateHolen(b, p, abruf.signal).then((z) => (zitate = z)).catch(() => {});
    return () => abruf.abort();
  });
  const zitiervorschlag = $derived(zitate ? zitate[zitierform.form] : "");
  async function zitiervorschlagKopieren() {
    zitatKopiert = (await kopieren(zitiervorschlag)) ? "ja" : "nein";
    setTimeout(() => (zitatKopiert = ""), RUECKMELDUNG_MS);
  }
  const vor = $derived(Math.max(0, Math.round((jetzt - gespeichertUm) / 1000)));

  function tippen() {
    clearTimeout(warten);
    warten = setTimeout(() => void jetztSpeichern(), SPEICHERN_NACH_MS);
  }

  /** Ausstehendes sofort speichern (auch beim Schließen); ohne Änderung nichts. */
  export async function jetztSpeichern(): Promise<void> {
    if (warten === undefined || weg) return laufend;
    clearTimeout(warten);
    warten = undefined;
    laufend = speichern(id, text);
    return laufend;
  }

  async function speichern(fuer: string, inhalt: string): Promise<void> {
    speichert = true;
    try {
      if (fuer) await notizAendern(fuer, inhalt);
      else if (entwurf && inhalt.trim()) id = (await notieren({ ...entwurf, text: inhalt })).id;
      gespeichertUm = Date.now();
      jetzt = gespeichertUm;
      fehler = "";
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      speichert = false;
    }
  }

  async function loeschen() {
    clearTimeout(warten);
    warten = undefined;
    weg = true;
    try {
      await laufend;                    // erst das laufende Speichern, sonst käme die Notiz danach zurück
      if (id) await notizLoeschen(id);
      onweg?.();
    } catch (f) {
      weg = false;
      fehler = seitenFehler(f);
    }
  }

  async function zitieren() {
    const buch = notiz ? (notiz.buch ? buchName(notiz.buch) : notiz.buch_name) : entwurf ? buchName(entwurf.buch) : "";
    kopiert = (await kopieren(zitatMitHerkunft(zitat, titel, abschnitt, buch))) ? "ja" : "nein";
    setTimeout(() => (kopiert = ""), RUECKMELDUNG_MS);
  }

  /** Beim Schließen (WIKI-54): eine Notiz am ganzen Artikel ohne Text und ohne Bilder sagt nichts und zählt nur mit;
   *  sie geht weg. An einer Stelle bleibt sie, dort markiert sie die Stelle. */
  export async function leerVerwerfen(): Promise<void> {
    await laufend;
    if (!id || weg || zitat || text.trim() || bilder.length || laedtHoch) return;
    weg = true;
    await notizLoeschen(id).catch(() => { weg = false; });
  }

  export function fokus() {
    feld?.focus();
  }
</script>

<div class="notiz-bearbeiten">
  <div class="feld-titel">Stelle</div>
  <div class="zitatbox">
    <span><b>{titel}</b>{abschnitt ? ` · ${abschnitt}` : ""}</span>
    {#if zitat}<span class="zitat">"{zitat}"</span>{:else}<span class="zitat">am ganzen Artikel</span>{/if}
  </div>
  <div class="notiz-feldkopf"><label class="feld-titel" for={feldId}>Notiz</label>
    <!-- Spracheingabe (WIKI-42): das Gesagte kommt hinten an den Text und wird gespeichert -->
    <span class="notiz-feldknoepfe">
      <button class="knopf still" title="Bild anfügen (oder ein Bildschirmfoto ins Textfeld einfügen)" onclick={() => dateiwahl?.click()}>
        <i class="fa-solid fa-image"></i><span class="wort">Bild</span></button>
      <input type="file" accept="image/*" multiple hidden bind:this={dateiwahl}
             onchange={(e) => { const f = e.currentTarget; void bilderAnfuegen([...(f.files ?? [])]); f.value = ""; }} />
      <Sprechknopf titel="Notiz sprechen" fertig={(t) => { text = text.trim() ? `${text.trimEnd()} ${t}` : t; tippen(); }} /></span></div>
  <textarea id={feldId} class="schreibfeld" bind:this={feld} bind:value={text} oninput={tippen} onpaste={einfuegen}
            ondragover={(e) => e.dataTransfer?.types.includes("Files") && e.preventDefault()}
            ondrop={(e) => { const neu = bilderAus(e.dataTransfer); if (neu.length) { e.preventDefault(); void bilderAnfuegen(neu); } }}
            placeholder={zitat ? "Ohne Text bleibt die Stelle markiert" : "Was du dir zum Artikel merken willst"}></textarea>
  <div class="gespeichert" class:fehlt={!!fehler}>
    {#if fehler}<i class="fa-solid fa-triangle-exclamation"></i>{fehler}
    {:else if laedtHoch}<i class="fa-solid fa-spinner fa-spin"></i>{laedtHoch === 1 ? "Ein Bild" : `${laedtHoch} Bilder`} in die Kellerwolke ...
    {:else if speichert}<i class="fa-solid fa-spinner fa-spin"></i>Speichert ...
    {:else if gespeichertUm}<i class="fa-solid fa-check"></i>Gespeichert {vor < 5 ? "gerade eben" : vor < 60 ? `vor ${vor} Sekunden` : `vor ${Math.round(vor / 60)} Minuten`}
    {:else}<i class="fa-solid fa-floppy-disk"></i>Speichert von selbst{/if}
  </div>
  {#if bilder.length}
    <div class="feld-titel">Bilder</div>
    <div class="notiz-bilder">
      {#each bilder as b, i (b.id)}
        <div class="notiz-bild">
          <button class="notiz-bild-zeigen" title="{b.name}, groß zeigen" onclick={() => (gross = i)}>
            <img src={notizBildAdresse(id, b.id)} alt={b.name} loading="lazy" /></button>
          <button class="notiz-bild-weg" class:scharf={entfernenFragen === b.id} onclick={() => bildEntfernen(b.id)}
                  title={entfernenFragen === b.id ? "Noch einmal: Bild entfernen" : "Bild entfernen"} aria-label="Bild entfernen">
            <i class="fa-solid {entfernenFragen === b.id ? 'fa-trash' : 'fa-xmark'}"></i></button>
        </div>
      {/each}
    </div>
  {/if}
  {#if belege.length || quelleUrl}
    <!-- Recherchemodus (WIKI-31): was die Stelle belegt und wo der Artikel im Netz steht -->
    <div class="feld-titel">Belege</div>
    <div class="belege">
      {#if quelleUrl}<a class="beleg-im-netz" href={quelleUrl} target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-globe"></i>Artikel im Netz</a>{/if}
      {#each belege as b (b.nummer)}
        <div class="beleg-zeile"><span class="nummer">{b.nummer}</span>
          <span>{b.text}{#if b.url} <a href={b.url} target="_blank" rel="noopener noreferrer" title={b.url}><i class="fa-solid fa-arrow-up-right-from-square"></i></a>{/if}</span></div>
      {/each}
      {#if zitiervorschlag}
        <div class="zitier-kopf">
          <Auswahl wert={zitierform.form} symbol="fa-quote-right" titel="Zitierform, bleibt auf diesem Gerät eingestellt"
                   optionen={ZITIERFORMEN} onwahl={zitierformMerken} />
          <button class="knopf still" class:kopiert-ok={zitatKopiert === "ja"} onclick={zitiervorschlagKopieren}>
            <i class="fa-{zitatKopiert === 'ja' ? 'solid fa-check' : zitatKopiert === 'nein' ? 'solid fa-triangle-exclamation' : 'regular fa-copy'}"></i>{zitatKopiert === "ja" ? "Kopiert" : zitatKopiert === "nein" ? "Geht nicht" : "Kopieren"}</button>
        </div>
        <div class="zitiervorschlag" class:block={zitierform.form === "bibtex"} title="Zitiervorschlag">{zitiervorschlag}</div>
      {/if}
    </div>
  {/if}
  {#if loeschenFragen}
    <div class="fundband warn"><i class="fa-solid fa-triangle-exclamation"></i>
      <span>{zitat ? "Notiz und Markierung löschen?" : "Notiz löschen?"}</span>
      <button class="knopf" onclick={loeschen}>Löschen</button><button class="knopf still" onclick={() => (loeschenFragen = false)}>Behalten</button></div>
  {:else}
    <div class="notiz-knoepfe">
      {#if zurStelle}<button class="knopf" onclick={zurStelle}><i class="fa-solid fa-arrow-up-right-from-square"></i>{zitat ? "Zur Stelle" : "Zum Artikel"}</button>{/if}
      {#if zitat}<button class="knopf" class:kopiert-ok={kopiert === "ja"} onclick={zitieren}
                         title="Zitat mit Artikel, Abschnitt und Quelle in die Zwischenablage">
        <i class="fa-solid {kopiert === 'ja' ? 'fa-check' : kopiert === 'nein' ? 'fa-triangle-exclamation' : 'fa-quote-right'}"></i>{kopiert === "ja" ? "Kopiert" : kopiert === "nein" ? "Geht nicht" : "Zitieren"}</button>{/if}
      {#if id}<button class="knopf gefahr" onclick={() => (loeschenFragen = true)}><i class="fa-solid fa-trash"></i>Löschen</button>{/if}
    </div>
  {/if}
</div>
{#if gross !== null && medien.length}
  <Leuchtkasten {medien} start={Math.min(gross, medien.length - 1)} titel={`an der Notiz zu ${titel}`} onzu={() => (gross = null)} />
{/if}
