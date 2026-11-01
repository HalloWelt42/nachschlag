<script lang="ts">
  // Ein Thema (Entwurf mockups/themen.html, rechte Seite): Kopf mit Beschreibung und Regel, Angebote der gespeicherten
  // Suche, Bereiche mit Artikeln als Karten oder Liste. Ziehen ordnet Artikel und Bereiche (am Rechner); in der Liste
  // wählt man den Bereich (überall, auch am Telefon).
  import Buchmarke from "./Buchmarke.svelte";
  import { Auswahl, geraet, hole, kopieren, navigation, Rueckfrage, seitenFehler } from "appkern-oberflaeche";
  import { RUECKMELDUNG_MS } from "../lib/zitat";
  import { ZITIERFORMEN, zitierform, zitierformMerken } from "../lib/recherche.svelte";
  import { untrack } from "svelte";
  import { bezeichnung, bibliothek, bibliothekLaden, buchName } from "../lib/bibliothek.svelte";
  import {
    ablehnen, angeboteHolen, austragen, bereichAendern, bereichAnlegen, bereichLoeschen, eintragen, standVon, themaAendern,
    themaHolen, themaLoeschen, verschieben, type Angebot, type Thema, type Themeneintrag,
  } from "../lib/themen.svelte";
  import { lesen } from "../lib/ziele";
  import Kachel from "./Kachel.svelte";

  let { id, ongeloescht }: { id: string; ongeloescht: () => void } = $props();

  /** Literaturliste (WIKI-31): Artikel mit Quellenangabe in der Zitierform des Geräts (einfach, APA, DIN ISO 690 als
   *  Markdown, oder BibTeX) und den gesammelten Belegen kopieren. Die Liste liegt vorher bereit: die Zwischenablage
   *  gibt es nur direkt im Klick, ohne Warten dazwischen. */
  let literatur = $state("");
  let literaturKopiert = $state<"" | "ja" | "nein">("");
  async function literaturLaden(thema: string, form: string) {
    try {
      literatur = (await hole<{ text: string }>(`/meins/themen/${encodeURIComponent(thema)}/literatur?form=${form}`)).text;
    } catch {
      literatur = "";
    }
  }
  $effect(() => void literaturLaden(id, zitierform.form));
  async function literaturKopieren() {
    literaturKopiert = literatur && (await kopieren(literatur)) ? "ja" : "nein";
    setTimeout(() => (literaturKopiert = ""), RUECKMELDUNG_MS);
    void literaturLaden(id, zitierform.form);   // für das nächste Mal mit den neuesten Notizen
  }

  type Ansicht = "karten" | "liste";
  const OHNE = "";                                      // Kennung für "ohne Bereich"

  let thema = $state.raw<Thema | null>(null);
  let angebote = $state.raw<Angebot[]>([]);
  let fehler = $state("");
  let ansicht = $state<Ansicht>("karten");
  let bearbeiten = $state<{ titel: string; beschreibung: string; regel: string; regel_buch: string } | null>(null);
  let loeschenFragen = $state(false);
  let neuerBereich = $state<string | null>(null);
  let umbenennen = $state<{ id: string; titel: string } | null>(null);
  let ziehe = $state<{ art: "eintrag" | "bereich"; id: string } | null>(null);
  let ziel = $state<{ bereich: string; platz: number } | null>(null);

  $effect(() => {
    const t = id;
    untrack(() => void laden(t));
  });

  async function laden(t = id) {
    try {
      const neu = await themaHolen(t);
      if (t !== id) return;
      thema = neu;
      navigation.titel = neu.titel;
      fehler = "";
      void angeboteLaden(t);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  async function angeboteLaden(t: string) {
    try {
      angebote = await angeboteHolen(t);
    } catch {
      angebote = [];                     // Angebote sind Beiwerk; ohne Suche bleibt das Thema benutzbar
    }
  }

  async function tun(arbeit: () => Promise<unknown>) {
    try {
      await arbeit();
      await laden();
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  const gruppen = $derived.by(() => {
    if (!thema) return [];
    const von = (b: string) => thema!.eintraege.filter((e) => e.bereich === b).sort((a, z) => a.platz - z.platz);
    const liste = thema.bereiche.map((b) => ({ id: b.id, titel: b.titel, eintraege: von(b.id) }));
    const ohne = von(OHNE);
    if (ohne.length || !liste.length) liste.push({ id: OHNE, titel: "Ohne Bereich", eintraege: ohne });
    return liste;
  });
  const bereichsWahl = $derived([...(thema?.bereiche ?? []).map((b) => ({ wert: b.id, titel: b.titel })), { wert: OHNE, titel: "Ohne Bereich" }]);

  // --- Kopf -----------------------------------------------------------------------------------------------------
  function bearbeitenBeginnen() {
    if (!thema) return;
    void bibliothekLaden();
    bearbeiten = { titel: thema.titel, beschreibung: thema.beschreibung, regel: thema.regel, regel_buch: thema.regel_buch };
  }

  async function speichern() {
    if (!bearbeiten?.titel.trim()) return;
    const werte = bearbeiten;
    await tun(() => themaAendern(id, werte));
    bearbeiten = null;
  }

  async function loeschen() {
    try {
      await themaLoeschen(id);
      ongeloescht();
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // --- Angebote -------------------------------------------------------------------------------------------------
  async function uebernehmen(a: Angebot) {
    angebote = angebote.filter((x) => x !== a);
    await tun(() => eintragen(id, { buch: a.buch, pfad: a.pfad, titel: a.titel, bild: a.bild }));
  }

  async function allesUebernehmen() {
    const alle = angebote;
    angebote = [];
    await tun(async () => {
      for (const a of alle) await eintragen(id, { buch: a.buch, pfad: a.pfad, titel: a.titel, bild: a.bild });
    });
  }

  async function passtNicht(a: Angebot) {
    angebote = angebote.filter((x) => x !== a);
    try {
      await ablehnen(id, a.buch, a.pfad);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // --- Bereiche -------------------------------------------------------------------------------------------------
  async function bereichNeu() {
    const titel = neuerBereich?.trim();
    neuerBereich = null;
    if (titel) await tun(() => bereichAnlegen(id, titel));
  }

  async function umbenannt() {
    const u = umbenennen;
    umbenennen = null;
    if (u?.titel.trim()) await tun(() => bereichAendern(id, u.id, { titel: u.titel.trim() }));
  }

  // --- Ziehen (am Rechner): Artikel vor eine Karte oder ans Ende eines Bereichs, Bereiche vor einen Bereich --------
  function ziehenBeginnen(e: DragEvent, art: "eintrag" | "bereich", kennung: string) {
    ziehe = { art, id: kennung };
    e.dataTransfer?.setData("text/plain", kennung);
    if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
  }

  function ueberKarte(e: DragEvent, bereich: string, platz: number) {
    if (ziehe?.art !== "eintrag") return;
    e.preventDefault();
    e.stopPropagation();
    ziel = { bereich, platz };
  }

  function ueberBereich(e: DragEvent, bereich: string, platz: number) {
    if (!ziehe) return;
    e.preventDefault();
    if (ziehe.art === "eintrag" && ziel?.bereich !== bereich) ziel = { bereich, platz };
    if (ziehe.art === "bereich") ziel = { bereich, platz };
  }

  async function ablegen(e: DragEvent) {
    e.preventDefault();
    const z = ziehe, an = ziel;
    ziehe = null;
    ziel = null;
    if (!z || !an || !thema) return;
    if (z.art === "eintrag") {
      const quelle = thema.eintraege.find((x) => x.id === z.id);
      const liste = gruppen.find((g) => g.id === an.bereich)?.eintraege ?? [];
      const vorher = liste.findIndex((x) => x.id === z.id);
      const platz = vorher >= 0 && vorher < an.platz ? an.platz - 1 : an.platz;   // ohne sich selbst gezählt
      if (quelle && (quelle.bereich !== an.bereich || vorher !== platz)) await tun(() => verschieben(id, z.id, an.bereich, platz));
    } else if (an.bereich !== OHNE) {
      const platz = thema.bereiche.findIndex((b) => b.id === an.bereich);
      const vorher = thema.bereiche.findIndex((b) => b.id === z.id);
      if (platz >= 0 && platz !== vorher) await tun(() => bereichAendern(id, z.id, { platz }));
    }
  }

  function ziehenEnde() {
    ziehe = null;
    ziel = null;
  }

  const oeffnen = (e: Themeneintrag) => e.buch && lesen(e.buch, e.pfad);
</script>

{#if fehler && !thema}
  <div class="fehlertext">{fehler}</div>
{:else if thema}
  <div class="thema-kopf">
    {#if bearbeiten}
      <div class="thema-formular">
        <label><span class="feld-titel">Titel</span><input class="eingabe" bind:value={bearbeiten.titel} maxlength="120" /></label>
        <label><span class="feld-titel">Beschreibung</span><textarea class="eingabe" rows="2" bind:value={bearbeiten.beschreibung} maxlength="1000"></textarea></label>
        <label><span class="feld-titel">Wächst mit der Suche</span>
          <input class="eingabe" bind:value={bearbeiten.regel} maxlength="400" placeholder="leer: nur von Hand" /></label>
        <div><span class="feld-titel">In welchen Quellen</span>
          <Auswahl bind:wert={bearbeiten.regel_buch} symbol="fa-book"
                   optionen={[{ wert: "", titel: "Alle Quellen" }, ...bibliothek.buecher.map((b) => ({ wert: b.kennung, titel: bezeichnung(b) }))]} /></div>
        <div class="thema-knoepfe">
          <button class="knopf primaer" disabled={!bearbeiten.titel.trim()} onclick={speichern}><i class="fa-solid fa-check"></i>Speichern</button>
          <button class="knopf still" onclick={() => (bearbeiten = null)}>Abbrechen</button>
          <button class="knopf gefahr rechts" onclick={() => (loeschenFragen = true)}><i class="fa-solid fa-trash"></i>Thema löschen</button>
        </div>
        {#if loeschenFragen}
          <Rueckfrage frage="Thema {thema.titel} löschen?" hinweis="Die Artikel bleiben in den Quellen, Merkzettel und Notizen bleiben."
                      knopf="Löschen" onabbrechen={() => (loeschenFragen = false)} onja={loeschen} />
        {/if}
      </div>
    {:else}
      {#if !geraet.mobil}<!-- am Telefon steht der Titel im Kopf, Bearbeiten in den Werkzeugen -->
        <h2>{thema.titel} <button class="rund still stift" title="Thema bearbeiten" onclick={bearbeitenBeginnen}><i class="fa-solid fa-pen"></i></button></h2>
      {/if}
      {#if thema.beschreibung}<p>{thema.beschreibung}</p>{/if}
      <div class="regel">
        {#if thema.regel}
          <span class="chip"><i class="fa-solid fa-wand-magic-sparkles"></i>wächst mit: "{thema.regel}"</span>
          <span class="chip aus"><i class="fa-solid fa-book"></i>{thema.regel_buch ? `nur ${buchName(thema.regel_buch)}` : "alle Quellen"}</span>
          <span class="neben">neue Treffer kommen als Vorschlag, nie von selbst</span>
        {:else}
          <span class="chip aus"><i class="fa-solid fa-hand"></i>von Hand</span>
          <button class="knopf still" onclick={bearbeitenBeginnen}><i class="fa-solid fa-wand-magic-sparkles"></i>Mit einer Suche wachsen lassen</button>
        {/if}
      </div>
    {/if}
    <div class="werkzeuge">
      {#if neuerBereich !== null}
        <form class="bereich-neu" onsubmit={(e) => { e.preventDefault(); void bereichNeu(); }}>
          <!-- svelte-ignore a11y_autofocus -->
          <input class="eingabe" bind:value={neuerBereich} placeholder="Name des Bereichs" maxlength="120" autofocus
                 onkeydown={(e) => e.key === "Escape" && (neuerBereich = null)} />
          <button class="knopf primaer" disabled={!neuerBereich.trim()}>Anlegen</button>
          <button type="button" class="knopf still" onclick={() => (neuerBereich = null)}>Abbrechen</button>
        </form>
      {:else}
        <button class="knopf" onclick={() => (neuerBereich = "")}><i class="fa-solid fa-folder-plus"></i><span class="wort">Bereich</span></button>
        {#if geraet.mobil && !bearbeiten}<button class="knopf" onclick={bearbeitenBeginnen}><i class="fa-solid fa-pen"></i><span class="wort">Bearbeiten</span></button>{/if}
        <button class="knopf" class:kopiert-ok={literaturKopiert === "ja"} onclick={literaturKopieren}
                title="Literaturliste in der gewählten Zitierform mit den Belegen aus den Notizen kopieren">
          <i class="fa-solid {literaturKopiert === 'ja' ? 'fa-check' : literaturKopiert === 'nein' ? 'fa-triangle-exclamation' : 'fa-list-ol'}"></i><span class="wort">{literaturKopiert === "ja" ? "Kopiert" : literaturKopiert === "nein" ? "Geht nicht" : "Literatur"}</span></button>
        <Auswahl wert={zitierform.form} symbol="fa-quote-right" titel="Zitierform der Literaturliste, bleibt auf diesem Gerät eingestellt"
                 optionen={ZITIERFORMEN} onwahl={zitierformMerken} />
      {/if}
      <div class="rechts">
        <span class="segment">
          <button class:aktiv={ansicht === "karten"} onclick={() => (ansicht = "karten")}><i class="fa-solid fa-grip"></i> Karten</button>
          <button class:aktiv={ansicht === "liste"} onclick={() => (ansicht = "liste")}><i class="fa-solid fa-list"></i> Liste</button>
        </span>
      </div>
    </div>
  </div>
  <div class="rollfeld" style="padding: 0">
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    {#if angebote.length}
      <div class="vorschlagsband">
        <div class="zeile1"><i class="fa-solid fa-wand-magic-sparkles"></i><b>{angebote.length} neu passend</b>
          <span class="neben">aus der Suche "{thema.regel}"</span>
          <button class="knopf still" onclick={allesUebernehmen}>Alle übernehmen</button></div>
        <div class="reihe">
          {#each angebote as a (a.buch + a.pfad)}
            <div class="angebot-artikel">
              {#if a.bild}<img src={a.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-file-lines"></i></span>{/if}
              <button class="angebot-ziel" onclick={() => lesen(a.buch, a.pfad)}><span class="t">{a.titel}</span>
                <!-- Ausschnitt vom Server: reiner Text, nur <em> -->
                <span class="u">{@html a.auszug || buchName(a.buch)}</span></button>
              <span class="ja-nein">
                <button class="rund ja" title="Übernehmen" onclick={() => uebernehmen(a)}><i class="fa-solid fa-check"></i></button>
                <button class="rund" title="Passt nicht, nicht wieder anbieten" onclick={() => passtNicht(a)}><i class="fa-solid fa-xmark"></i></button>
              </span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
    {#if !thema.eintraege.length}
      <p class="leer-hinweis thema-leer">Noch keine Artikel. Im Artikel oben "Thema" wählen{thema.regel ? " oder oben Vorschläge übernehmen" : ""}.</p>
    {/if}
    <div class="thema-bereiche" role="list" ondragend={ziehenEnde}>
      {#each gruppen as g, gi (g.id)}
        <section class:ziel={ziehe?.art === "bereich" && ziel?.bereich === g.id && g.id !== OHNE} role="listitem"
                 ondragover={(e) => ueberBereich(e, g.id, ziehe?.art === "bereich" ? gi : g.eintraege.length)} ondrop={ablegen}>
          <div class="bereich-kopf">
            {#if g.id !== OHNE}
              <span class="griff" draggable="true" title="Ziehen zum Umordnen" role="button" tabindex="-1"
                    ondragstart={(e) => ziehenBeginnen(e, "bereich", g.id)}><i class="fa-solid fa-grip-vertical"></i></span>
            {:else}<i class="fa-solid fa-inbox ohne"></i>{/if}
            {#if umbenennen?.id === g.id}
              <form class="bereich-neu" onsubmit={(e) => { e.preventDefault(); void umbenannt(); }}>
                <!-- svelte-ignore a11y_autofocus -->
                <input class="eingabe" bind:value={umbenennen.titel} maxlength="120" autofocus onkeydown={(e) => e.key === "Escape" && (umbenennen = null)} />
                <button class="knopf primaer">Speichern</button>
              </form>
            {:else}
              <h3>{g.titel}</h3><span class="zahl">{g.eintraege.length}</span>
            {/if}
            {#if g.id !== OHNE && umbenennen?.id !== g.id}
              <span class="rechts">
                <button class="rund" title="Umbenennen" onclick={() => (umbenennen = { id: g.id, titel: g.titel })}><i class="fa-solid fa-pen"></i></button>
                <button class="rund" title="Bereich auflösen; seine Artikel bleiben im Thema" onclick={() => tun(() => bereichLoeschen(id, g.id))}><i class="fa-solid fa-folder-minus"></i></button>
              </span>
            {/if}
          </div>
          {#if ansicht === "karten"}
            <div class="thema-karten">
              {#each g.eintraege as e, ei (e.id)}
                {@const stand = standVon(e)}
                <Kachel art="quer" bild={e.bild} titel={e.titel} gesperrt={!e.buch} ziel={() => oeffnen(e)}
                       class={[ziehe?.id === e.id && "zieht", ziel?.bereich === g.id && ziel.platz === ei && ziehe?.art === "eintrag" && "davor"].filter(Boolean).join(" ")}
                       hinweis={e.buch ? "Öffnen; ziehen zum Umordnen" : "Die Quelle gibt es nicht mehr in der Bibliothek"}
                       draggable="true" ondragstart={(d: DragEvent) => ziehenBeginnen(d, "eintrag", e.id)} ondragover={(d: DragEvent) => ueberKarte(d, g.id, ei)}>
                  <span class="stand-zeile">{#if stand.art === "notiz"}<i class="fa-solid fa-note-sticky marke-notiz"></i>{:else if stand.art === "gelesen"}<i class="fa-solid fa-circle-check gelesen"></i>{/if}{stand.text}</span>
                  {#snippet ecke()}<i class="fa-solid fa-grip-vertical griff"></i>{/snippet}
                </Kachel>
              {/each}
              {#if !g.eintraege.length}
                <div class="leer-bereich" class:ziel={ziel?.bereich === g.id && ziehe?.art === "eintrag"}><i class="fa-solid fa-arrow-down"></i>Artikel hierher ziehen</div>
              {:else if ziel?.bereich === g.id && ziel.platz === g.eintraege.length && ziehe?.art === "eintrag"}
                <div class="leer-bereich ziel"><i class="fa-solid fa-arrow-down"></i>Hier ablegen</div>
              {/if}
            </div>
          {:else}
            <div class="liste">
              {#each g.eintraege as e (e.id)}
                {@const stand = standVon(e)}
                <div class="liste-zeile">
                  <button class="liste-ziel" disabled={!e.buch} onclick={() => oeffnen(e)}>
                    {#if e.bild}<img src={e.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-file-lines"></i></span>{/if}
                    <span><span class="t">{e.titel}</span><span class="u"><Buchmarke kennung={e.buch} ersatz={e.buch_name} symbol={false} /> · {stand.text}</span></span>
                  </button>
                  <Auswahl wert={e.bereich} klein symbol="fa-folder" titel="Bereich" optionen={bereichsWahl}
                           onwahl={(b) => b !== e.bereich && tun(() => verschieben(id, e.id, b, Number.MAX_SAFE_INTEGER))} />
                  <button class="rund" title="Aus dem Thema nehmen" onclick={() => tun(() => austragen(id, e.id))}><i class="fa-solid fa-xmark"></i></button>
                </div>
              {/each}
              {#if !g.eintraege.length}<p class="leer-hinweis" style="padding-inline: var(--a4)">Keine Artikel in diesem Bereich.</p>{/if}
            </div>
          {/if}
        </section>
      {/each}
    </div>
  </div>
{/if}
