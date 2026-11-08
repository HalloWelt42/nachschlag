<script lang="ts">
  // Vorlagen (Entwurf mockups/export-vorlage.html): eine Vorlage beschreibt ein Buch in drei Teilen. Aufbau (welche Teile
  // in welcher Reihenfolge, je Teil aus den Büchern oder von der KI), Anweisung an die KI (Ton, Vorgaben, eigener Zusatz,
  // feste Regeln) und Gestaltung. Mitgelieferte sind fest und lassen sich als eigene kopieren; jede eigene ist eine Datei
  // in der Ablage (Kellerwolke oder Datenordner) und wird nach jeder Änderung gespeichert. Weg: themen/<thema>/buch/vorlagen?vorlage=<kennung>.
  import { untrack } from "svelte";
  import { Auswahl, gehe, geraet, navigation, Rueckfrage, seitenFehler } from "appkern-oberflaeche";
  import Buchdeckel from "./Buchdeckel.svelte";
  import { geloeschtWird, inKellerwolke } from "../lib/ablage";
  import {
    BILDER, FARBEN, FUER_WEN, HERKUNFT, LAENGE, TON, buecher, datum, vorlageDatei, vorlageKopieren, vorlageLoeschen, vorlagenLaden,
    vorlageSpeichern, type Teil, type Teilart, type Vorlage,
  } from "../lib/buecher.svelte";

  let { thema }: { thema: string } = $props();

  type Platz = "vorn" | "innen" | "hinten";
  const SPEICHERN_MS = 600;
  const EINMALIG = new Set<Teilart>(["titelseite", "inhalt", "kapiteleinleitung", "blick", "umgeformt", "originaltext", "notizen",
                                      "fragen", "glossar", "literatur"]);

  let v = $state<Vorlage | null>(null);
  let gespeichert = "";                                      // Stand, der in der Ablage liegt (zum Vergleich)
  let zustand = $state<{ art: "" | "speichert" | "gespeichert" | "fehler"; text: string }>({ art: "", text: "" });
  let neu = $state<string | null>(null);
  let loeschenFragen = $state(false);
  let kasten = $state<{ platz: number | null; titel: string; anweisung: string } | null>(null);
  let ziehe = $state<{ platz: Platz; i: number } | null>(null);
  let fehler = $state("");

  const gewaehlt = $derived(new URLSearchParams(navigation.suche).get("vorlage") ?? "");
  const katalog = $derived(Object.fromEntries((buecher.katalog?.teile ?? []).map((t) => [t.art, t])));
  const fest = $derived(!v || v.mitgeliefert);

  async function laden() {
    try {
      await vorlagenLaden();
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }
  $effect(() => untrack(() => void laden()));

  // Wahl aus der Adresse (sonst die erste); bearbeitet wird eine Kopie, gespeichert nur, was sich geändert hat
  $effect(() => {
    const kennung = gewaehlt;
    const liste = buecher.vorlagen;
    untrack(() => {
      const quelle = liste.find((x) => x.kennung === kennung) ?? liste[0];
      if (!quelle || quelle.kennung === v?.kennung) return;
      v = structuredClone($state.snapshot(quelle)) as Vorlage;
      gespeichert = JSON.stringify(v);
      zustand = { art: "", text: "" };
      navigation.titel = "Vorlagen";
    });
  });

  $effect(() => {
    if (!v || v.mitgeliefert) return;
    const jetzt = $state.snapshot(v) as Vorlage;
    if (JSON.stringify(jetzt) === gespeichert) return;
    const takt = setTimeout(async () => {
      zustand = { art: "speichert", text: "" };
      try {
        const neuer = await vorlageSpeichern(jetzt);
        gespeichert = JSON.stringify(jetzt);
        buecher.vorlagen = buecher.vorlagen.map((x) => (x.kennung === neuer.kennung ? neuer : x));
        zustand = { art: "gespeichert", text: "" };
      } catch (f) {
        zustand = { art: "fehler", text: seitenFehler(f) };
      }
    }, SPEICHERN_MS);
    return () => clearTimeout(takt);
  });

  const waehlen = (kennung: string) => gehe(`themen/${thema}/buch/vorlagen?vorlage=${kennung}`, true);

  async function kopieren() {
    const titel = neu?.trim();
    if (!v || !titel) return;
    try {
      const kopie = await vorlageKopieren(v.kennung, titel);
      neu = null;
      await vorlagenLaden();
      waehlen(kopie.kennung);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  async function loeschen() {
    if (!v) return;
    try {
      await vorlageLoeschen(v.kennung);
      loeschenFragen = false;
      if (buecher.entwuerfe[thema]?.vorlage === v.kennung) buecher.entwuerfe[thema].vorlage = "lernheft";
      v = null;
      await vorlagenLaden();
      waehlen(buecher.vorlagen[0]?.kennung ?? "");
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // --- Aufbau --------------------------------------------------------------------------------------------------------
  const titelVonTeil = (t: Teil) => (t.art === "kasten" ? `Je Artikel: ${t.titel}` : katalog[t.art]?.titel ?? t.art);
  const vorhanden = $derived(new Set(v ? [...v.aufbau.vorn, ...v.aufbau.innen, ...v.aufbau.hinten].map((t) => t.art) : []));
  const angebot = $derived((buecher.katalog?.teile ?? [])
    .filter((t) => t.ebene !== "gliederung" && (t.art === "kasten" || !vorhanden.has(t.art))
      && !(t.wechsel && vorhanden.has(t.wechsel) && t.ebene === "artikel"))
    .map((t) => ({ wert: t.art, titel: t.art === "kasten" ? "Eigener Kasten je Artikel" : t.titel, hinweis: HERKUNFT[t.herkunft] })));

  function hinzufuegen(art: Teilart) {
    if (!v) return;
    if (art === "kasten") {
      kasten = { platz: null, titel: "", anweisung: "" };
      return;
    }
    const ebene = katalog[art]?.ebene;
    const teil: Teil = { art, titel: "", anweisung: "" };
    if (ebene === "artikel") imKapitel(teil);
    else if (art === "kapiteleinleitung") v.aufbau.innen.unshift(teil);
    else if (ebene === "kapitel") v.aufbau.innen.push(teil);
    else if (art === "titelseite") v.aufbau.vorn.unshift(teil);
    else if (art === "inhalt") v.aufbau.vorn.push(teil);
    else v.aufbau.hinten.push(teil);
  }

  // ein Teil je Artikel hinter den letzten Teil je Artikel (Kapitelteile am Ende bleiben am Ende)
  function imKapitel(teil: Teil) {
    if (!v) return;
    const innen = v.aufbau.innen;
    const letzter = innen.reduce((n, t, i) => (katalog[t.art]?.ebene === "artikel" ? i : n), -1);
    innen.splice(letzter >= 0 ? letzter + 1 : innen.length, 0, teil);
  }

  function kastenFertig() {
    if (!v || !kasten || !kasten.titel.trim() || !kasten.anweisung.trim()) return;
    const teil: Teil = { art: "kasten", titel: kasten.titel.trim(), anweisung: kasten.anweisung.trim() };
    if (kasten.platz === null) imKapitel(teil);
    else v.aufbau.innen[kasten.platz] = teil;
    kasten = null;
  }

  function wechseln(platz: Platz, i: number) {
    const t = v?.aufbau[platz][i];
    const andere = t && katalog[t.art]?.wechsel;
    if (v && t && andere) v.aufbau[platz][i] = { ...t, art: andere };
  }

  function ablegen(platz: Platz, ziel: number) {
    if (!v || !ziehe || ziehe.platz !== platz || ziehe.i === ziel) return;
    const liste = v.aufbau[platz];
    const [t] = liste.splice(ziehe.i, 1);
    liste.splice(ziel, 0, t);
    ziehe = null;
  }

  const mitgeliefert = $derived(buecher.vorlagen.filter((x) => x.mitgeliefert));
  const eigene = $derived(buecher.vorlagen.filter((x) => !x.mitgeliefert));
</script>

{#snippet zeile(platz: Platz, t: Teil, i: number)}
  {@const angabe = katalog[t.art]}
  <div class="teil" class:innen={platz === "innen"} class:zieht={ziehe?.platz === platz && ziehe.i === i} role="listitem"
       draggable={!fest} ondragstart={() => (ziehe = { platz, i })} ondragover={(e) => e.preventDefault()} ondrop={() => ablegen(platz, i)}
       ondragend={() => (ziehe = null)}>
    <i class="fa-solid fa-grip-vertical griff" class:unsichtbar={fest} title={fest ? "" : "Ziehen ändert die Reihenfolge"}></i>
    {#if t.art === "kasten" && !fest}
      <button class="exp-teilname" title={t.anweisung} onclick={() => (kasten = { platz: i, titel: t.titel, anweisung: t.anweisung })}>{titelVonTeil(t)} <i class="fa-solid fa-pen"></i></button>
    {:else}<span title={t.anweisung || angabe?.beschreibung}>{titelVonTeil(t)}</span>{/if}
    {#if angabe?.wechsel && !fest}
      <button class="herkunft" class:ki={angabe.herkunft === "ki"} title="Wechseln: {katalog[angabe.wechsel]?.titel}" onclick={() => wechseln(platz, i)}>
        {HERKUNFT[angabe.herkunft]} <i class="fa-solid fa-arrow-right-arrow-left"></i></button>
    {:else}<span class="herkunft" class:ki={angabe?.herkunft === "ki"}>{angabe ? HERKUNFT[angabe.herkunft] : ""}</span>{/if}
    {#if fest}<span></span>{:else}<button class="rund still" title="Entfernen" onclick={() => v!.aufbau[platz].splice(i, 1)}><i class="fa-solid fa-xmark"></i></button>{/if}
  </div>
{/snippet}

{#if !geraet.mobil}<!-- am Telefon stehen Titel und Zurück im Kopf der Schale -->
  <div class="seiten-kopf">
    <button class="rund still" title="Zurück zu Als Buch" onclick={() => gehe(`themen/${thema}/buch`)}><i class="fa-solid fa-chevron-left"></i></button>
    <h1>Vorlagen</h1>
  </div>
{/if}
<div class="rollfeld">
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  <div class="exp-zweispaltig">
    <div class="exp-vorlagenwahl">
      <div class="gruppe">Mitgeliefert</div>
      {#each mitgeliefert as x (x.kennung)}
        <button class="eintrag" class:aktiv={x.kennung === v?.kennung} onclick={() => waehlen(x.kennung)}><i class="fa-solid {x.symbol}"></i><span>{x.titel}</span><span class="u">{x.ki ? "KI" : ""}</span></button>
      {/each}
      <div class="gruppe">Eigene</div>
      {#each eigene as x (x.kennung)}
        <button class="eintrag" class:aktiv={x.kennung === v?.kennung} onclick={() => waehlen(x.kennung)}><i class="fa-solid {x.symbol}"></i><span>{x.titel}</span><span class="u">{x.ki ? "KI" : ""}</span></button>
      {:else}<p class="exp-leise">Noch keine. Eine eigene entsteht als Kopie.</p>{/each}
      {#if neu === null}
        <button class="knopf still exp-neu" disabled={!v} onclick={() => (neu = v ? `${v.titel} (eigene)` : "")}><i class="fa-solid fa-plus"></i>Neue Vorlage</button>
      {:else}
        <form class="exp-neu-form" onsubmit={(e) => { e.preventDefault(); void kopieren(); }}>
          <!-- svelte-ignore a11y_autofocus -->
          <input class="eingabe" bind:value={neu} maxlength="60" placeholder="Name der Vorlage" autofocus onkeydown={(e) => e.key === "Escape" && (neu = null)} />
          <span class="exp-leise">als Kopie von {v?.titel}</span>
          <span class="knopfzeile"><button class="knopf primaer" disabled={!neu.trim()}>Anlegen</button><button type="button" class="knopf still" onclick={() => (neu = null)}>Abbrechen</button></span>
        </form>
      {/if}
      {#if buecher.hinweis}<p class="exp-hinweis">{buecher.hinweis}</p>{/if}
    </div>

    {#if v}
      <div class="exp-schritte">
        <div class="exp-datei">
          <i class="fa-solid {v.symbol} exp-akzent"></i>
          {#if fest}<b class="exp-dateititel">{v.titel}</b>{:else}<input class="eingabe exp-dateititel" bind:value={v.titel} maxlength="60" aria-label="Name der Vorlage" />{/if}
          <span>{v.mitgeliefert ? "mitgeliefert und fest; zum Ändern kopieren" : v.kopiert_aus ? `kopiert aus ${v.kopiert_aus} am ${datum(v.kopiert_am)}` : "eigene Vorlage"}</span>
          <span class="rechts">
            {#if zustand.art === "speichert"}<span class="exp-leise"><i class="fa-solid fa-spinner fa-spin"></i> speichert</span>
            {:else if zustand.art === "gespeichert"}<span class="exp-leise"><i class="fa-solid fa-check"></i> gespeichert</span>{/if}
            <button class="knopf still" onclick={() => (neu = `${v!.titel} (eigene)`)}><i class="fa-solid fa-copy"></i>Kopieren</button>
            {#if !v.mitgeliefert}<button class="knopf still" onclick={() => (loeschenFragen = true)}><i class="fa-solid fa-trash"></i>Löschen</button>{/if}
          </span>
        </div>
        {#if zustand.art === "fehler"}<div class="fehlertext">{zustand.text}</div>{/if}
        {#if loeschenFragen}
          <Rueckfrage frage="Vorlage {v.titel} löschen?" hinweis="Die Datei {geloeschtWird(false)}; fertige Bücher bleiben."
                      knopf="Löschen" onabbrechen={() => (loeschenFragen = false)} onja={loeschen} />
        {/if}

        <div class="karte">
          <h2><i class="fa-solid fa-list-ol"></i>Aufbau<span class="neben">{fest ? "fest" : "Ziehen ändert die Reihenfolge"}</span></h2>
          <div class="exp-teile" role="list">
            {#each v.aufbau.vorn as t, i (i)}{@render zeile("vorn", t, i)}{/each}
            <div class="teil" role="listitem">
              <i class="fa-solid fa-grip-vertical griff unsichtbar"></i><span><b>{katalog[v.aufbau.gliederung]?.titel}</b></span>
              {#if fest}<span class="herkunft">{HERKUNFT.thema}</span>
              {:else}<button class="herkunft" title="Wechseln: {katalog[v.aufbau.gliederung === 'kapitel' ? 'abc' : 'kapitel']?.titel}"
                              onclick={() => (v!.aufbau.gliederung = v!.aufbau.gliederung === "kapitel" ? "abc" : "kapitel")}>{HERKUNFT.thema} <i class="fa-solid fa-arrow-right-arrow-left"></i></button>{/if}
              <span></span>
            </div>
            {#each v.aufbau.innen as t, i (i)}{@render zeile("innen", t, i)}{/each}
            {#each v.aufbau.hinten as t, i (i)}{@render zeile("hinten", t, i)}{/each}
            <div class="teil fest" role="listitem"><i class="fa-solid fa-grip-vertical griff unsichtbar"></i><span>Quellen und Lizenzen</span><span class="herkunft"><i class="fa-solid fa-lock"></i> immer am Ende</span><span></span></div>
          </div>
          {#if kasten}
            <form class="exp-kastenform" onsubmit={(e) => { e.preventDefault(); kastenFertig(); }}>
              <label><span class="feld-titel">Überschrift des Kastens</span><input class="eingabe" bind:value={kasten.titel} maxlength="80" placeholder="etwa So beobachtest du es" /></label>
              <label><span class="feld-titel">Was die KI hineinschreibt</span><textarea class="eingabe exp-freitext" bind:value={kasten.anweisung} maxlength="1000"
                     placeholder="etwa: ob und womit man es selbst sieht; steht dazu nichts im Artikel, bleibt der Kasten leer"></textarea></label>
              <span class="knopfzeile"><button class="knopf primaer" disabled={!kasten.titel.trim() || !kasten.anweisung.trim()}>{kasten.platz === null ? "Hinzufügen" : "Übernehmen"}</button>
                <button type="button" class="knopf still" onclick={() => (kasten = null)}>Abbrechen</button></span>
            </form>
          {:else if !fest && angebot.length}
            <div class="exp-hinzu"><Auswahl wert="" symbol="fa-plus" platzhalter="Teil hinzufügen" titel="Teil hinzufügen" optionen={angebot} onwahl={(w) => hinzufuegen(w as Teilart)} /></div>
          {/if}
        </div>

        <div class="karte">
          <h2><i class="fa-solid fa-wand-magic-sparkles"></i>Anweisung an die KI{#if !v.ki}<span class="neben">diese Vorlage braucht keine KI</span>{/if}</h2>
          <div class="feld"><div class="was"><div class="name">Ton</div></div>
            <span class="segment">{#each TON as x (x.wert)}<button class:aktiv={v.anweisung.ton === x.wert} disabled={fest} onclick={() => (v!.anweisung.ton = x.wert)}>{x.titel}</button>{/each}</span></div>
          <div class="feld"><div class="was"><div class="name">Vorgabe für wen und Länge</div><div class="beschreibung">Vorgabe; beim Bauen eines Buchs änderbar.</div></div>
            <span class="wert-rechts">
              {#if fest}
                <span class="chip">{FUER_WEN.find((x) => x.wert === v!.anweisung.fuer_wen)?.titel}</span>
                <span class="chip">{LAENGE.find((x) => x.wert === v!.anweisung.laenge)?.titel}</span>
                <span class="chip">{v.anweisung.fragen} Fragen</span>
              {:else}
                <Auswahl wert={v.anweisung.fuer_wen} klein symbol="fa-user" titel="Für wen" optionen={FUER_WEN} onwahl={(w) => (v!.anweisung.fuer_wen = w)} />
                <Auswahl wert={v.anweisung.laenge} klein symbol="fa-ruler-horizontal" titel="Länge" optionen={LAENGE} onwahl={(w) => (v!.anweisung.laenge = w)} />
                <span class="wert-zahl"><button class="knopf" title="Weniger Fragen" disabled={v.anweisung.fragen <= 0} onclick={() => (v!.anweisung.fragen -= 1)}><i class="fa-solid fa-minus"></i></button>
                  <b>{v.anweisung.fragen}</b><button class="knopf" title="Mehr Fragen" disabled={v.anweisung.fragen >= 10} onclick={() => (v!.anweisung.fragen += 1)}><i class="fa-solid fa-plus"></i></button> Fragen</span>
              {/if}
            </span></div>
          <div class="feld"><div class="was"><div class="name">Zusatz in eigenen Worten</div><div class="beschreibung">Geht so an das Modell, nach den festen Regeln.</div></div>
            <textarea class="exp-freitext" bind:value={v.anweisung.zusatz} maxlength="2000" readonly={fest} aria-label="Zusatz in eigenen Worten"
                      placeholder="etwa: bei jedem Himmelsobjekt sagen, ob und womit man es selbst sieht"></textarea></div>
          <div class="feld"><div class="was"><div class="name">Feste Regeln</div><div class="beschreibung">Gelten für jede Vorlage und lassen sich nicht abschalten.</div></div>
            <span class="exp-regeln">{#each buecher.katalog?.regeln ?? [] as r (r)}<span class="chip"><i class="fa-solid fa-check"></i>{r}</span>{/each}</span></div>
        </div>

        <div class="karte">
          <h2><i class="fa-solid fa-palette"></i>Gestaltung</h2>
          <div class="feld"><div class="was"><div class="name">Schrift im Text</div></div>
            <span class="segment"><button class:aktiv={v.gestaltung.schrift === "serifen"} disabled={fest} onclick={() => (v!.gestaltung.schrift = "serifen")}>Mit Serifen</button>
              <button class:aktiv={v.gestaltung.schrift === "ohne"} disabled={fest} onclick={() => (v!.gestaltung.schrift = "ohne")}>Ohne Serifen</button></span></div>
          <div class="feld"><div class="was"><div class="name">Farbe der Kästen</div><div class="beschreibung">Für Auf einen Blick, Fragen und Überschriften; im PDF auch druckbar in Grau.</div></div>
            <span class="exp-farben" role="radiogroup" aria-label="Farbe">
              {#each FARBEN as f (f)}<button class:an={v.gestaltung.farbe === f} role="radio" aria-checked={v.gestaltung.farbe === f} aria-label={f} disabled={fest}
                                             style="background: var(--{f})" onclick={() => (v!.gestaltung.farbe = f)}></button>{/each}
            </span></div>
          <div class="feld"><div class="was"><div class="name">Bilder</div></div>
            <span class="segment">{#each BILDER as x (x.wert)}<button class:aktiv={v.gestaltung.bilder === x.wert} disabled={fest} onclick={() => (v!.gestaltung.bilder = x.wert)}>{x.titel}</button>{/each}</span></div>
          <div class="feld"><div class="was"><div class="name">So sieht eine Seite aus</div></div>
            <div class="exp-buch exp-buch-klein">
              <Buchdeckel titel="Sternenhimmel" untertitel={v.untertitel} />
              <div class="exp-seite" class:serifen={v.gestaltung.schrift === "serifen"} style="--exp-farbe: var(--{v.gestaltung.farbe})">
                <b>Saturn</b>
                {#if vorhanden.has("blick")}<div class="kasten"><em>Auf einen Blick</em>Der sechste Planet, nach Jupiter der zweitgrößte.</div>{/if}
                {#each v.aufbau.innen.filter((t) => t.art === "kasten").slice(0, 1) as k (k.titel)}<div class="kasten"><em>{k.titel}</em>{k.anweisung}</div>{/each}
                <span>Saturn ist von der Sonne aus der sechste Planet ...</span>
              </div>
            </div></div>
        </div>

        <div class="exp-datei">
          <i class="fa-solid fa-file-code"></i><span>{v.mitgeliefert ? "Mitgeliefert, im Programm" : "Liegt als Datei"}</span>
          <code>{v.mitgeliefert ? `${v.kennung}.toml` : `${inKellerwolke() ? "Kellerwolke" : "Datenordner"} / ${buecher.ordner.replace(/^Apps\//, "").split("/").join(" / ")} / ${v.kennung}.toml`}</code>
          <span class="rechts"><a class="knopf still" href={vorlageDatei(v.kennung)} download="{v.kennung}.toml"><i class="fa-solid fa-share-nodes"></i>Weitergeben</a></span>
        </div>
      </div>
    {/if}
  </div>
</div>
