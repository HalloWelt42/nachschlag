<script lang="ts">
  // Eine Notiz bearbeiten (Entwurf mockups/notizen.html, rechte Leiste; am Telefon im Blatt): Stelle, Text, speichert
  // von selbst. Eine neue Notiz am ganzen Artikel kommt als `entwurf` und entsteht erst mit dem ersten Text; eine Notiz
  // an einer Stelle gibt es schon (als Markierung), sobald die Stelle markiert ist.
  import { onDestroy, untrack } from "svelte";
  import { seitenFehler } from "appkern-oberflaeche";
  import { buchName } from "../lib/bibliothek.svelte";
  import { kopieren } from "../lib/kopieren";
  import { notieren, notizAendern, notizLoeschen, type Notiz, type NotizNeu } from "../lib/meins.svelte";

  const SPEICHERN_NACH_MS = 700;
  const ZEIT_TAKT_MS = 5000;

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
  let warten: ReturnType<typeof setTimeout> | undefined;
  let feld = $state<HTMLTextAreaElement>();
  const feldId = $props.id();

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
  const vor = $derived(Math.max(0, Math.round((jetzt - gespeichertUm) / 1000)));

  function tippen() {
    clearTimeout(warten);
    warten = setTimeout(() => void jetztSpeichern(), SPEICHERN_NACH_MS);
  }

  /** Ausstehendes sofort speichern (auch beim Schließen); ohne Änderung nichts. */
  export async function jetztSpeichern(): Promise<void> {
    if (warten === undefined) return;
    clearTimeout(warten);
    warten = undefined;
    const fuer = id, inhalt = text;
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
    try {
      if (id) await notizLoeschen(id);
      onweg?.();
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  function zitieren() {
    const buch = notiz ? (notiz.buch ? buchName(notiz.buch) : notiz.buch_name) : entwurf ? buchName(entwurf.buch) : "";
    void kopieren(`"${zitat}" (${[titel, abschnitt, buch].filter(Boolean).join(", ")})`);
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
  <label class="feld-titel" for={feldId}>Notiz</label>
  <textarea id={feldId} class="schreibfeld" bind:this={feld} bind:value={text} oninput={tippen}
            placeholder={zitat ? "Ohne Text bleibt die Stelle markiert" : "Was du dir zum Artikel merken willst"}></textarea>
  <div class="gespeichert" class:fehlt={!!fehler}>
    {#if fehler}<i class="fa-solid fa-triangle-exclamation"></i>{fehler}
    {:else if speichert}<i class="fa-solid fa-spinner fa-spin"></i>Speichert ...
    {:else if gespeichertUm}<i class="fa-solid fa-check"></i>Gespeichert {vor < 5 ? "gerade eben" : vor < 60 ? `vor ${vor} Sekunden` : `vor ${Math.round(vor / 60)} Minuten`}
    {:else}<i class="fa-solid fa-floppy-disk"></i>Speichert von selbst{/if}
  </div>
  {#if loeschenFragen}
    <div class="fundband warn"><i class="fa-solid fa-triangle-exclamation"></i>
      <span>{zitat ? "Notiz und Markierung löschen?" : "Notiz löschen?"}</span>
      <button class="knopf" onclick={loeschen}>Löschen</button><button class="knopf still" onclick={() => (loeschenFragen = false)}>Behalten</button></div>
  {:else}
    <div class="notiz-knoepfe">
      {#if zurStelle}<button class="knopf" onclick={zurStelle}><i class="fa-solid fa-arrow-up-right-from-square"></i>{zitat ? "Zur Stelle" : "Zum Artikel"}</button>{/if}
      {#if zitat}<button class="knopf" onclick={zitieren}><i class="fa-solid fa-quote-right"></i>Zitieren</button>{/if}
      {#if id}<button class="knopf gefahr" onclick={() => (loeschenFragen = true)}><i class="fa-solid fa-trash"></i>Löschen</button>{/if}
    </div>
  {/if}
</div>
