<script lang="ts">
  // Eigene Bücher (Entwurf mockups/export-buecher.html, am Telefon telefon-export.html): oben das Buch, das gerade
  // entsteht (ein Auftrag wie jeder andere, mit Stufen je Kapitel, Tempo und Hinweisen der Prüfung), darunter das Regal
  // der fertigen Bücher. Hat sich ein Thema seit dem Bau geändert, bietet die Karte das Nachbauen an (nur Neues wird
  // umgeformt). Weg buecher/<kennung>: ein Buch lesen.
  import { onMount } from "svelte";
  import {
    auftragAbbrechen, auftraege, auftragWiederholen, beiAuftrag, gehe, geraet, hole, navigation, Rueckfrage, seitenFehler, type Auftrag,
  } from "appkern-oberflaeche";
  import Buchdeckel from "../teile/Buchdeckel.svelte";
  import {
    buchDatei, buchLoeschen, buecher, datum, dauerText, leseansichtHolen, nachbauen, regalLaden, uhrzeit, type Baustand, type Eigenbuch,
  } from "../lib/buecher.svelte";

  const NACHSEHEN_MS = 4000;
  let fehler = $state("");
  let menue = $state("");
  let hinweiseOffen = $state("");
  let loeschenFragen = $state<Eigenbuch | null>(null);
  let lesen = $state<{ id: string; titel: string; untertitel: string; html: string } | null>(null);

  const gewaehlt = $derived(navigation.teile[0] ?? "");
  const regal = $derived(buecher.regal);
  const laeuft = $derived(!!regal?.laufend.some((s) => s.zustand === "laeuft" || s.zustand === "wartet"));
  const ordner = $derived(regal ? regal.ablage.replace(/^Apps\//, "").split("/").join(" / ") : "");

  async function laden() {
    try {
      await regalLaden();
      fehler = "";
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // Lesen: ein Buch in der App, aus seinem Inhalt (Bilder aus den Büchern der Bibliothek)
  $effect(() => {
    const id = gewaehlt;
    if (!id) {
      lesen = null;
      return;
    }
    leseansichtHolen(id).then((l) => { lesen = { id, ...l }; navigation.titel = l.titel; }).catch((f) => (fehler = seitenFehler(f)));
  });

  onMount(() => {
    void laden();
    const takt = setInterval(() => { if (laeuft) void laden(); }, NACHSEHEN_MS);
    const aus = beiAuftrag((a: Auftrag) => { if (a.art === "buchbau" && ["fertig", "fehler", "abgebrochen"].includes(a.zustand)) void laden(); });
    return () => { clearInterval(takt); aus(); };
  });

  async function tun(arbeit: () => Promise<unknown>) {
    try {
      await arbeit();
      await laden();
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  function imAuftrag(s: Baustand) {
    auftraege.gewaehlt = s.auftrag;
    gehe("auftraege");
  }

  function pille(s: Baustand): { klasse: string; symbol: string; text: string } {
    if (s.zustand === "laeuft") return { klasse: "aktiv", symbol: "fa-circle-play", text: s.begonnen ? `läuft seit ${uhrzeit(s.begonnen)}` : "läuft" };
    if (s.zustand === "wartet") return { klasse: "warn", symbol: "fa-moon", text: s.grund || "wartet" };
    if (s.zustand === "abgebrochen") return { klasse: "warn", symbol: "fa-pause", text: "angehalten" };
    return { klasse: "warn", symbol: "fa-triangle-exclamation", text: s.zustand === "fehler" ? "gescheitert" : "unterbrochen" };
  }

  const kapitelJetzt = (s: Baustand) => {
    const kapitel = s.stufen.filter((x) => !x.titel.startsWith("Glossar") && !x.titel.startsWith("Satz"));
    const nr = kapitel.findIndex((x) => x.zustand === "jetzt");
    return nr >= 0 ? `Kapitel ${nr + 1} von ${kapitel.length}` : s.zustand === "wartet" ? "wartet" : "entsteht";
  };
  const groesse = (bytes: number) => (bytes > 1_048_576 ? `${(bytes / 1_048_576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);
</script>

<svelte:window onclick={() => (menue = "")} />

<div class="inhalt-stufe" data-schrift="klein">
{#if gewaehlt}
  <div class="seiten-kopf">
    {#if !geraet.mobil}<button class="rund still" title="Zurück zu Eigene Bücher" onclick={() => gehe("buecher")}><i class="fa-solid fa-chevron-left"></i></button>{/if}
    <h1>{lesen?.titel ?? "Buch"}</h1>
    {#if lesen?.untertitel}<span class="pille"><i class="fa-solid fa-book"></i>{lesen.untertitel}</span>{/if}
  </div>
  <div class="rollfeld">
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    {#if lesen}<article class="artikel exp-lesen">{@html lesen.html}</article>{/if}
  </div>
{:else}
  {#if !geraet.mobil}<div class="seiten-kopf"><h1>Eigene Bücher</h1></div>{/if}
  <div class="rollfeld">
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    {#if regal}
      {#if geraet.mobil}
        <!-- Telefon: was entsteht, mit Balken; fertige Bücher öffnen im EPUB-Leser des Telefons -->
        <div class="exp-t-liste">
          {#each regal.laufend as s (s.auftrag)}
            <div class="exp-t-buch">
              <Buchdeckel bild={s.titelbild} titel={s.titel} />
              <div><div class="t">{s.titel}</div><div class="u">{s.vorlage_titel}, {s.zustand === "laeuft" ? `entsteht: ${kapitelJetzt(s)}` : pille(s).text}</div>
                <div class="exp-spur"><span style="width: {Math.round(s.anteil * 100)}%"></span></div></div>
            </div>
          {/each}
          {#each regal.fertig as b (b.id)}
            {@const datei = b.formate.find((f) => f.format === "epub") ?? b.formate[0]}
            <a class="exp-t-buch" href={datei ? buchDatei(b.id, datei.format) : undefined} download>
              <Buchdeckel bild={b.titelbild} titel={b.titel} />
              <div><div class="t">{b.titel}</div><div class="u">{b.vorlage_titel}, {b.seiten} Seiten</div>
                {#if b.veraltet}<div class="u exp-info"><i class="fa-solid fa-circle-info"></i> {b.veraltet.text.replace("Thema geändert: ", "")}, nachbauen</div>{/if}</div>
            </a>
          {/each}
        </div>
      {:else}
        <div class="exp-buecher">
          {#each regal.laufend as s (s.auftrag)}
            {@const p = pille(s)}
            <div class="exp-lage">
              <div>
                <div class="zustand"><b>{s.titel}</b><span class="pille {p.klasse}"><i class="fa-solid {p.symbol}"></i>{p.text}</span></div>
                <div class="beschreibung">{s.beschreibung}</div>
              </div>
              <div class="aktionen">
                {#if s.zustand === "laeuft" || s.zustand === "wartet"}
                  <button class="knopf" onclick={() => tun(() => auftragAbbrechen(s.auftrag))}><i class="fa-solid fa-pause"></i>Anhalten</button>
                {:else}
                  <button class="knopf" onclick={() => tun(() => auftragWiederholen(s.auftrag))}><i class="fa-solid fa-play"></i>Fortsetzen</button>
                  <button class="knopf still" onclick={() => tun(() => hole(`/auftraege/${s.auftrag}`, { method: "DELETE" }))}><i class="fa-solid fa-xmark"></i>Verwerfen</button>
                {/if}
                <button class="rund" title="Im Auftrag ansehen" onclick={() => imAuftrag(s)}><i class="fa-solid fa-list-check"></i></button>
              </div>
              <div class="zahlen">
                <div class="kennzahl"><span class="k">Umgeformt</span><span class="w">{Math.round(s.anteil * 100)} %</span><span class="exp-spur"><span style="width: {Math.round(s.anteil * 100)}%"></span></span></div>
                <div class="kennzahl"><span class="k">Tempo</span><span class="w">{s.tempo ? `${Math.round(s.tempo)} Z/s` : "-"}</span></div>
                <div class="kennzahl"><span class="k">Fertig gegen</span><span class="w">{s.fertig_gegen && s.zustand === "laeuft" ? uhrzeit(s.fertig_gegen) : "-"}</span></div>
                <div class="kennzahl"><span class="k">Prüfung</span><span class="w">{s.hinweise ? `${s.hinweise} ${s.hinweise === 1 ? "Hinweis" : "Hinweise"}` : "ohne Hinweis"}</span></div>
              </div>
              {#if s.grund && s.zustand !== "wartet"}<p class="exp-hinweis">{s.grund}</p>{/if}
              {#if s.stufen.length}
                <div class="exp-stufen">
                  {#each s.stufen as st, i (i)}
                    <div class="stufe {st.zustand}">
                      <i class={st.zustand === "fertig" ? "fa-solid fa-circle-check" : st.zustand === "jetzt" ? "fa-solid fa-circle-play" : "fa-regular fa-circle"}></i>
                      <span>{st.titel}</span><span class="exp-spur"><span style="width: {Math.round((st.zustand === 'fertig' ? 1 : st.anteil) * 100)}%"></span></span>
                      <span class="zahl">{st.text}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}

          <div class="exp-abschnitt"><h2>Fertig</h2><span>{regal.fertig.length} {regal.fertig.length === 1 ? "Buch" : "Bücher"}, in der Kellerwolke unter {ordner}</span></div>
          {#if !regal.fertig.length}
            <p class="leer-hinweis">Noch keine Bücher. Im Thema oben "Als Buch" wählen: Vorlage, Probekapitel, dann jetzt oder heute Nacht bauen.</p>
          {/if}
          <div class="exp-regal">
            {#each regal.fertig as b (b.id)}
              <div class="exp-buchkarte">
                <Buchdeckel bild={b.titelbild} titel={b.titel} untertitel={b.vorlage_titel} />
                <div class="koerper">
                  <span class="t">{b.titel}</span>
                  <span class="u">{b.artikel} Artikel, {b.seiten} Seiten, {datum(b.gebaut)}</span>
                  <span class="formate">{#each b.formate as f (f.format)}<span title="{groesse(f.groesse)}, {f.pfad}">{f.titel}</span>{/each}</span>
                  {#if b.hinweise.length}
                    <button class="exp-pruefhinweis" onclick={() => (hinweiseOffen = hinweiseOffen === b.id ? "" : b.id)}>
                      <i class="fa-solid fa-triangle-exclamation"></i> Prüfung: {b.hinweise.length} {b.hinweise.length === 1 ? "Hinweis" : "Hinweise"}</button>
                  {/if}
                  <span class="aktionen">
                    <button class="knopf" onclick={() => gehe(`buecher/${b.id}`)}><i class="fa-solid fa-book-open"></i>Lesen</button>
                    {#each b.formate as f (f.format)}
                      <a class="rund" title="{f.titel} herunterladen ({groesse(f.groesse)})" href={buchDatei(b.id, f.format)} download>
                        <i class="fa-solid {f.format === 'pdf' ? 'fa-file-pdf' : 'fa-download'}"></i></a>
                    {/each}
                    <span class="exp-menue-anker">
                      <button class="rund" title="Mehr" onclick={(e) => { e.stopPropagation(); menue = menue === b.id ? "" : b.id; }}><i class="fa-solid fa-ellipsis"></i></button>
                      {#if menue === b.id}
                        <span class="exp-menue">
                          <button onclick={() => gehe(`themen/${b.thema}/buch`)}><i class="fa-solid fa-layer-group"></i>Zum Thema, als Buch</button>
                          <button onclick={() => tun(() => nachbauen(b.id, "nachts"))}><i class="fa-solid fa-moon"></i>Heute Nacht neu bauen</button>
                          <button class="gefahr" onclick={() => (loeschenFragen = b)}><i class="fa-solid fa-trash"></i>Löschen</button>
                        </span>
                      {/if}
                    </span>
                  </span>
                </div>
                {#if hinweiseOffen === b.id}
                  <ul class="exp-hinweisliste">{#each b.hinweise as h, i (i)}<li><b>{h.artikel}:</b> {h.art === "satz" ? `"${h.text}" steht so nicht im Original` : h.art === "zahl" ? `die Zahl ${h.text} steht nicht im Original` : `ohne Beleg: ${h.text}`}</li>{/each}</ul>
                {/if}
                {#if b.veraltet}
                  <div class="veraltet"><i class="fa-solid fa-circle-info"></i><span>{b.veraltet.text}</span>
                    <button class="knopf still" onclick={() => tun(() => nachbauen(b.id, "jetzt"))}><i class="fa-solid fa-rotate"></i>Nachbauen, etwa {dauerText(b.veraltet.sekunden)}</button></div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/if}
  </div>
  {#if loeschenFragen}
    {@const b = loeschenFragen}
    <Rueckfrage frage="Buch {b.titel} ({b.vorlage_titel}) löschen?" hinweis="Die Dateien gehen in den Papierkorb der Kellerwolke; das Thema bleibt."
                knopf="Löschen" onabbrechen={() => (loeschenFragen = null)} onja={() => tun(async () => { await buchLoeschen(b.id); loeschenFragen = null; })} />
  {/if}
{/if}
</div>
