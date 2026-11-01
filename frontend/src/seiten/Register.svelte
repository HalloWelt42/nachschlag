<script lang="ts">
  // Register (WIKI-39, docs/SUCHE.md Punkt 10): Schlagwörter und Autoren der Frage-Antwort-Bücher, über alle Bücher oder
  // eines. Wege: /register (Schlagwörter), /register/autoren, /register/schlagwoerter/<wort>, /register/autoren/<buch>/<nr>;
  // das Buch steht in ?buch=. Schlagwörter und Autorennamen in den Fragen führen hierher. Listen seitenweise.
  import { Auswahl, gehe, geraet, navigation, seitenFehler } from "appkern-oberflaeche";
  import { onMount, untrack } from "svelte";
  import { bezeichnung, bibliothek, bibliothekLaden, datum, zahl } from "../lib/bibliothek.svelte";
  import { autorenHolen, autorHolen, fragenZumSchlagwort, schlagwoerterHolen } from "../lib/schnittstelle";
  import type { AutorEintrag, AutorSeite, RegisterFrage, SchlagwortEintrag, Sortierung } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";
  import Buchmarke from "../teile/Buchmarke.svelte";
  import Fragekarte from "../teile/Fragekarte.svelte";

  const ANZAHL = 60;

  onMount(() => void bibliothekLaden());          // Namen der Bücher für Buchwahl und Buchmarken

  const teile = $derived(navigation.teile);
  const ansicht = $derived(teile[0] === "schlagwoerter" && teile[1] ? "schlagwort" : teile[0] === "autoren" && teile[2] ? "autor"
                           : teile[0] === "autoren" ? "autoren" : "schlagwoerter");
  const buch = $derived(ansicht === "autor" ? teile[1] : new URLSearchParams(navigation.suche).get("buch") ?? "");
  const fragebuecher = $derived(bibliothek.buecher.filter((b) => b.art === "frage_antwort"));
  const buchwahl = $derived([{ wert: "", titel: "Alle Frage-Antwort-Quellen" }, ...fragebuecher.map((b) => ({ wert: b.kennung, titel: bezeichnung(b) }))]);

  let anfang = $state("");
  let sortierung = $state<Sortierung>("stimmen");
  let woerter = $state.raw<SchlagwortEintrag[]>([]);
  let autoren = $state.raw<AutorEintrag[]>([]);
  let fragen = $state.raw<RegisterFrage[]>([]);
  let autor = $state.raw<AutorSeite | null>(null);
  let gesamt = $state(0);
  let ohneIndex = $state<string[]>([]);
  let laedt = $state(false);
  let fehler = $state("");

  /** Lädt die erste Seite (oder hängt mit `weiter` die nächste an); die Antwort zählt nur, wenn die Ansicht noch dieselbe ist. */
  let stand = 0;
  async function laden(weiter = false) {
    const mein = ++stand;
    laedt = true;
    try {
      if (ansicht === "schlagwoerter") {
        const s = await schlagwoerterHolen(buch, anfang, weiter ? woerter.length : 0, ANZAHL);
        if (mein !== stand) return;
        woerter = weiter ? [...woerter, ...s.eintraege] : s.eintraege;
        gesamt = s.gesamt;
        ohneIndex = s.ohne_index;
      } else if (ansicht === "autoren") {
        const s = await autorenHolen(buch, anfang, weiter ? autoren.length : 0, ANZAHL);
        if (mein !== stand) return;
        autoren = weiter ? [...autoren, ...s.eintraege] : s.eintraege;
        gesamt = s.gesamt;
        ohneIndex = s.ohne_index;
      } else if (ansicht === "schlagwort") {
        const s = await fragenZumSchlagwort(teile[1], buch, sortierung, weiter ? fragen.length : 0);
        if (mein !== stand) return;
        fragen = weiter ? [...fragen, ...s.eintraege] : s.eintraege;
        gesamt = s.gesamt;
        ohneIndex = s.ohne_index;
      } else {
        const s = await autorHolen(teile[1], teile[2], weiter ? (autor?.beitraege.length ?? 0) : 0);
        if (mein !== stand) return;
        autor = weiter && autor ? { ...s, beitraege: [...autor.beitraege, ...s.beitraege] } : s;
        gesamt = s.gesamt;
        ohneIndex = [];
      }
      fehler = "";
    } catch (f) {
      if (mein === stand) fehler = seitenFehler(f);
    } finally {
      if (mein === stand) laedt = false;
    }
  }

  // Neu laden, wenn Weg, Buch, Filter oder Sortierung wechseln; der Filter wartet kurz aufs Tippen
  let warten: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    void [ansicht, buch, teile.join("/"), sortierung, anfang];
    clearTimeout(warten);
    warten = setTimeout(() => untrack(() => void laden()), 200);
    return () => clearTimeout(warten);
  });
  $effect(() => {
    navigation.titel = ansicht === "schlagwort" ? `Schlagwort ${teile[1]}` : ansicht === "autor" ? autor?.autor.autor ?? "Autor" : "Register";
  });

  function weg(ziel: string, mitBuch = buch) {
    gehe(mitBuch ? `${ziel}?${new URLSearchParams({ buch: mitBuch })}` : ziel);
  }

  const zeitraum = (a: AutorEintrag) => !a.von ? "" : a.von.slice(0, 4) === a.bis.slice(0, 4) ? a.von.slice(0, 4) : `${a.von.slice(0, 4)} bis ${a.bis.slice(0, 4)}`;
  const mehr = $derived(ansicht === "schlagwoerter" ? woerter.length < gesamt : ansicht === "autoren" ? autoren.length < gesamt
                        : ansicht === "schlagwort" ? fragen.length < gesamt : (autor?.beitraege.length ?? 0) < gesamt);
</script>

<div class="inhalt-stufe" data-schrift="klein">
  <div class="rollfeld" style="padding: 0">
    <div class="register-seite">
      {#if ansicht === "schlagwoerter" || ansicht === "autoren"}
        <div class="meins-kopf">
          {#if !geraet.mobil}<h1>Register</h1>{/if}
          <div class="register-reiter" role="tablist">
            <button role="tab" aria-selected={ansicht === "schlagwoerter"} class:aktiv={ansicht === "schlagwoerter"}
                    onclick={() => weg("register")}><i class="fa-solid fa-tags"></i>Schlagwörter</button>
            <button role="tab" aria-selected={ansicht === "autoren"} class:aktiv={ansicht === "autoren"}
                    onclick={() => weg("register/autoren")}><i class="fa-solid fa-user-pen"></i>Autoren</button>
          </div>
        </div>
        <div class="register-filter">
          <Auswahl wert={buch} symbol="fa-book" titel="Welche Quellen" optionen={buchwahl} onwahl={(w: string) => weg(ansicht === "autoren" ? "register/autoren" : "register", w)} />
          <label class="suchfeld register-anfang"><i class="fa-solid fa-filter"></i>
            <input type="search" bind:value={anfang} placeholder={ansicht === "autoren" ? "Name beginnt mit" : "Schlagwort beginnt mit"}
                   aria-label="Filter" /></label>
          <span class="register-zahl">{zahl(gesamt)} {ansicht === "autoren" ? (gesamt === 1 ? "Autor" : "Autoren") : (gesamt === 1 ? "Schlagwort" : "Schlagwörter")}</span>
        </div>
      {:else}
        <div class="meins-kopf">
          <button class="knopf still" onclick={() => weg(ansicht === "autor" ? "register/autoren" : "register", ansicht === "autor" ? "" : buch)}>
            <i class="fa-solid fa-arrow-left"></i>Register</button>
        </div>
      {/if}

      {#each ohneIndex as k (k)}
        <div class="fundband"><i class="fa-solid fa-hourglass-half"></i>
          <span><Buchmarke kennung={k} />: noch ohne eigenen Index, mit ihm entsteht das Register. Große Quellen beginnen erst,
            wenn die Grenze unter Einstellungen, Suche darüber liegt.</span>
          <button class="knopf still" onclick={() => gehe("auftraege")}>Aufträge</button>
          <button class="knopf still" onclick={() => gehe("einstellungen/suche")}>Einstellungen</button></div>
      {/each}
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}

      {#if ansicht === "schlagwoerter"}
        <div class="register-woerter">
          {#each woerter as w (w.wort)}
            <a class="register-wort" href={`/register/schlagwoerter/${encodeURIComponent(w.wort)}${buch ? `?buch=${encodeURIComponent(buch)}` : ""}`}
               onclick={(e) => { e.preventDefault(); weg(`register/schlagwoerter/${encodeURIComponent(w.wort)}`); }}>
              <span class="wort">{w.wort}</span><span class="zahl-klein">{zahl(w.fragen)}</span></a>
          {/each}
        </div>
      {:else if ansicht === "autoren"}
        <div class="register-liste">
          {#each autoren as a (a.buch + a.schluessel)}
            <a class="register-zeile" href={`/register/autoren/${encodeURIComponent(a.buch)}/${encodeURIComponent(a.schluessel)}`}
               onclick={(e) => { e.preventDefault(); gehe(`register/autoren/${encodeURIComponent(a.buch)}/${encodeURIComponent(a.schluessel)}`); }}>
              <span class="name">{a.autor}</span>
              {#if !buch}<Buchmarke kennung={a.buch} />{/if}
              <span class="werte"><span><b>{zahl(a.beitraege)}</b>Beiträge</span><span><b>{zahl(a.stimmen)}</b>Stimmen</span>
                {#if zeitraum(a)}<span class="zeit">{zeitraum(a)}</span>{/if}</span>
            </a>
          {/each}
        </div>
      {:else if ansicht === "schlagwort"}
        <div class="register-titel">
          <h1><span class="wort">{teile[1]}</span></h1>
          <span class="register-zahl">{zahl(gesamt)} {gesamt === 1 ? "Frage" : "Fragen"}{buch ? "" : " in allen Frage-Antwort-Quellen"}</span>
          <div class="register-sortierung" role="tablist">
            <button role="tab" aria-selected={sortierung === "stimmen"} class:aktiv={sortierung === "stimmen"} onclick={() => (sortierung = "stimmen")}>Meiste Stimmen</button>
            <button role="tab" aria-selected={sortierung === "neueste"} class:aktiv={sortierung === "neueste"} onclick={() => (sortierung = "neueste")}>Neueste</button>
          </div>
        </div>
        <div class="fragenliste">
          {#each fragen as f (f.buch + f.pfad)}
            <Fragekarte buch={f.buch} frage={f} mitBuch={!buch} />
          {/each}
        </div>
      {:else if autor}
        <div class="register-titel">
          <h1>{autor.autor.autor}</h1>
          <Buchmarke kennung={autor.autor.buch} />
          <div class="register-werte">
            <span><b>{zahl(autor.autor.beitraege)}</b>Beiträge</span>
            <span><b>{zahl(autor.autor.fragen)}</b>Fragen</span>
            <span><b>{zahl(autor.autor.antworten)}</b>Antworten</span>
            {#if autor.autor.akzeptiert}<span class="gut"><b>{zahl(autor.autor.akzeptiert)}</b>akzeptiert</span>{/if}
            <span><b>{zahl(autor.autor.stimmen)}</b>Stimmen</span>
            {#if autor.autor.von}<span><b>{datum(autor.autor.von)}</b>bis {datum(autor.autor.bis)}</span>{/if}
          </div>
        </div>
        <div class="register-liste">
          {#each autor.beitraege as b, i (b.pfad + b.art + i)}
            <a class="register-zeile" href={"/" + lesenZiel(autor.autor.buch, b.pfad)}
               onclick={(e) => { e.preventDefault(); lesen(autor!.autor.buch, b.pfad); }}>
              <span class="art" title={b.art === "frage" ? "Frage" : "Antwort"}>
                <i class="fa-solid {b.art === 'frage' ? 'fa-circle-question' : b.akzeptiert ? 'fa-circle-check' : 'fa-reply'}" class:gut={b.akzeptiert}></i></span>
              <span class="name">{b.titel}</span>
              <span class="werte"><span><b>{zahl(b.stimmen)}</b>Stimmen</span>{#if b.datum}<span class="zeit">{b.datum}</span>{/if}</span>
            </a>
          {/each}
        </div>
      {/if}

      {#if mehr}
        <button class="knopf register-mehr" disabled={laedt} onclick={() => laden(true)}>
          <i class="fa-solid {laedt ? 'fa-spinner fa-spin' : 'fa-angles-down'}"></i>Mehr laden</button>
      {:else if laedt}
        <div class="leer"><i class="fa-solid fa-spinner fa-spin"></i> lädt ...</div>
      {/if}
    </div>
  </div>
</div>
