// Entwürfe WIKI-89: baut aus echten Zufallsfunden (daten/funde.json, aus den Probebüchern gezogen) die Varianten der
// Zufallskacheln. Jede Seite nennt ihre Variante in <body data-variante>. Nur für die Entwürfe, kein Teil der App.

const VARIANTEN = [
  ["bildkarte", "1 Bildkarte", "Jede Karte bekommt oben das erste Bild des Artikels; ohne Bild das Symbol des Buchs freigestellt auf der Farbe seiner Art. Auszug drei Zeilen, Knöpfe als Zeichen. Gegen die Flut: nur dichter, sonst alle Karten."],
  ["stapel", "2 Spielkarten-Stapel", "Die oberste Reihe steht voll. Jede weitere Reihe liegt wie Spielkarten darunter, nur ihr Kopf (Buchsymbol und Titel) schaut heraus. Fährt die Maus darüber, hebt sich die Karte heraus; am Telefon per Tipp."],
  ["faecher", "3 Fächer je Buch", "Je Buch ein kleiner Stapel aus drei Funden. Hover fächert ihn auf, so sieht man drei Titel auf einmal; die vordere Karte ist der aktuelle Fund. Weniger Kacheln, mehr Auswahl."],
  ["leit", "4 Leitkarte und Mosaik", "Ein Fund groß mit Bild und Text, die übrigen als Bildmosaik ohne Text. Der Auszug erscheint beim Darüberfahren auf dem Bild; ein Tipp macht ein Feld zur Leitkarte."],
  ["magazin", "5 Magazin nach Art", "Wie eine Zeitung: je Art von Buch eine Rubrik mit einem Aufmacher (Bild, Auszug) und kurzen Meldungen darunter (nur Titel). Ordnet die Flut nach Themen statt nach Büchern."],
  ["pult", "6 Liste mit Lesepult", "Links eine ruhige Liste (kleines Bild, Titel, Buch), rechts ein Lesepult mit Bild und Auszug des gewählten Funds. Viele Funde passen auf eine Bildschirmhöhe, gelesen wird nur einer."],
  ["wende", "7 Wendekarten", "Vorn nur Bild und Titel, groß und ruhig; beim Darüberfahren (am Telefon per Tipp) dreht sich die Karte und zeigt Auszug und Knöpfe. Viel Bild, wenig Text auf einen Blick."],
  ["runde", "8 Eine Runde", "Statt aller Bücher nur vier Funde je Runde, aus verschiedenen Büchern gemischt; der Würfel mischt neu, Chips wählen die Arten. Die Flut entsteht gar nicht erst."],
];

const ZEICHEN = { enzyklopaedie: "fa-book", dokumentation: "fa-code", uebung: "fa-graduation-cap", anleitung: "fa-screwdriver-wrench",
                  frage_antwort: "fa-comments", dateiformat: "fa-file-code" };
const ART_NAME = { enzyklopaedie: "Nachschlagewerke", dokumentation: "Dokumentation", uebung: "Übungen", anleitung: "Anleitungen",
                   frage_antwort: "Frage und Antwort", dateiformat: "Dateiformate" };
const e = (t) => String(t).replace(/[&<>"]/g, (z) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[z]);

function titelbild(f, klasse = "") {
  if (f.bild) return `<div class="titelbild ${klasse}"><img class="foto" src="${f.bild}" alt="" loading="lazy"></div>`;
  const symbol = f.symbol ? `<img class="gross" src="${f.symbol}" alt="">` : `<i class="fa-solid ${ZEICHEN[f.art]} gross"></i>`;
  return `<div class="titelbild ohne ${klasse}"><span class="wasser">${e(f.titel.trim()[0] ?? "")}</span>${symbol}</div>`;
}
const buchzeile = (f) => `<span class="buchzeile">${f.symbol ? `<img src="${f.symbol}" alt="">` : `<i class="fa-solid ${ZEICHEN[f.art]}"></i>`}<span>${e(f.buch)}</span></span>`;
const knoepfe = () => `<span style="display:flex;gap:6px"><button class="knopf-sym" title="Lesen"><i class="fa-solid fa-book-open"></i></button>` +
  `<button class="knopf-sym" title="Neuer Zufall"><i class="fa-solid fa-rotate"></i></button></span>`;
const auszug = (f) => `<span class="auszug">${e(f.auszug)}</span>`;

const BAUEN = {
  bildkarte: (fs) => `<div class="v-bildkarte">${fs.map((f) => `
    <div class="kachel hoch art-${f.art}" data-karte>${titelbild(f)}
      <div class="kachel-koerper"><span class="kachel-titel">${e(f.titel)}</span>${auszug(f)}
        <div class="kachel-fuss">${buchzeile(f)}${knoepfe()}</div></div></div>`).join("")}</div>`,

  stapel: (fs) => {
    const spalten = Math.max(1, Math.floor((document.querySelector(".entwurf").clientWidth + 16) / 256));
    return `<div class="v-stapel">${fs.map((f, i) => `
      <div class="kachel karte art-${f.art} ${i >= spalten ? "unten" : ""}" tabindex="0" style="--ebene:${100 - Math.floor(i / spalten)}" onclick="this.classList.toggle('offen')">
        <div class="kopfband">${f.symbol ? `<img src="${f.symbol}" alt="">` : `<i class="fa-solid ${ZEICHEN[f.art]}"></i>`}<span class="t">${e(f.titel)}</span></div>
        ${titelbild(f)}<div class="koerper">${buchzeile(f)}${auszug(f)}</div></div>`).join("")}</div>`;
  },

  faecher: (fs) => {
    const je = {};
    for (const f of fs) (je[f.buch] ??= []).push(f);
    return `<div class="v-faecher">${Object.values(je).map((liste) => {
      // fehlen Funde, liegen Rückseiten dahinter (Farbe der Art, Symbol des Buchs): der Stapel bleibt ein Stapel
      const drei = [null, null, ...liste].slice(-3);
      const vorn = liste[0];
      return `<div class="faecher">${drei.map((f, i) => f ? `
        <div class="kachel karte art-${f.art}">${titelbild(f)}<div class="koerper"><span class="kachel-titel">${e(f.titel)}</span>
          ${i === 2 ? buchzeile(f) + auszug(f) : ""}</div></div>` : `
        <div class="kachel karte ruecken art-${vorn.art}">${titelbild({ ...vorn, bild: "", titel: vorn.buch })}</div>`).join("")}
        <span class="chip zahl-k">${liste.length > 1 ? "3 Funde" : "1 Fund"}</span></div>`;
    }).join("")}</div>`;
  },

  leit: (fs) => {
    const leit = fs.find((f) => f.bild) ?? fs[0];
    return `<div class="v-leit">
      <div class="kachel leitkarte art-${leit.art}">${titelbild(leit)}<div class="koerper"><span class="fund-etikett"><i class="fa-solid fa-dice"></i>Zufallsfund</span>
        <span class="kachel-titel" style="font-size:var(--titel)">${e(leit.titel)}</span>${buchzeile(leit)}<span class="auszug" style="-webkit-line-clamp:6">${e(leit.auszug)}</span>
        <div class="knopfreihe"><button class="knopf"><i class="fa-solid fa-book-open"></i>Lesen</button><button class="knopf still"><i class="fa-solid fa-rotate"></i>Neuer Zufall</button></div></div></div>
      <div class="mosaik">${fs.filter((f) => f !== leit).map((f) => `
        <div class="feld art-${f.art}" title="${e(f.titel)}">${titelbild(f)}<span class="band">${e(f.titel)}</span>
          <span class="hover-text"><b>${e(f.titel)}</b><br>${e(f.auszug.slice(0, 160))} ...</span></div>`).join("")}</div></div>`;
  },

  magazin: (fs) => {
    const je = {};
    for (const f of fs) (je[f.art] ??= []).push(f);
    return `<div class="v-magazin">${Object.entries(je).map(([art, liste]) => {
      const auf = liste.find((f) => f.bild) ?? liste[0];
      return `<section class="rubrik art-${art}"><div class="rubrik-kopf"><i class="fa-solid ${ZEICHEN[art]}"></i>${ART_NAME[art]}</div>
        <div class="aufmacher">${titelbild(auf)}<div class="koerper"><span class="kachel-titel">${e(auf.titel)}</span>${buchzeile(auf)}${auszug(auf)}</div></div>
        ${liste.filter((f) => f !== auf).map((f) => `<div class="meldung">${titelbild(f)}<span><span class="kachel-titel">${e(f.titel)}</span>${buchzeile(f)}</span></div>`).join("")}
      </section>`;
    }).join("")}</div>`;
  },

  pult: (fs) => `<div class="v-pult">
    <div class="pult-liste">${fs.map((f, i) => `
      <button class="zeile art-${f.art} ${i === 0 ? "an" : ""}" data-nr="${i}">${titelbild(f)}<span style="min-width:0"><span class="t">${e(f.titel)}</span>${buchzeile(f)}</span></button>`).join("")}</div>
    <div class="kachel pult"></div></div>`,

  wende: (fs) => `<div class="v-wende">${fs.map((f) => `
    <div class="wende art-${f.art}" onclick="this.classList.toggle('offen')"><div class="innen">
      <div class="seite-v">${titelbild(f)}<span class="band"><span class="t">${e(f.titel)}</span>${buchzeile(f)}</span></div>
      <div class="seite-h"><span class="kachel-titel">${e(f.titel)}</span>${buchzeile(f)}${auszug(f)}<div class="kachel-fuss">${knoepfe()}</div></div>
    </div></div>`).join("")}</div>`,

  runde: (fs) => {
    const arten = [...new Set(fs.map((f) => f.art))];
    const runde = [fs[11], fs[6], fs[3], fs[1]].filter(Boolean);
    return `<div class="v-runde" style="display:flex;flex-direction:column;gap:var(--a3)">
      <div class="runde-leiste"><button class="knopf haupt wuerfel"><i class="fa-solid fa-dice"></i>Neu mischen</button>
        ${arten.map((a) => `<span class="chip wahl an"><i class="fa-solid ${ZEICHEN[a]}"></i>${ART_NAME[a]}</span>`).join("")}
        <span class="rest">4 von ${fs.length} Büchern · Leertaste mischt neu</span></div>
      <div class="reihe-r">${runde.map((f) => `<div class="kachel hoch art-${f.art}" data-karte>${titelbild(f)}
        <div class="kachel-koerper"><span class="kachel-titel">${e(f.titel)}</span>${buchzeile(f)}${auszug(f)}<div class="kachel-fuss">${knoepfe()}</div></div></div>`).join("")}</div></div>`;
  },
};

function pultZeigen(fs, nr) {
  const f = fs[nr], pult = document.querySelector(".pult");
  pult.className = `kachel pult art-${f.art}`;
  pult.innerHTML = `${titelbild(f)}<div class="koerper"><span class="fund-etikett"><i class="fa-solid fa-dice"></i>Zufallsfund</span>
    <span class="kachel-titel" style="font-size:var(--titel)">${e(f.titel)}</span>${buchzeile(f)}<span class="auszug" style="-webkit-line-clamp:8">${e(f.auszug)}</span>
    <div class="knopfreihe"><button class="knopf"><i class="fa-solid fa-book-open"></i>Lesen</button><button class="knopf still"><i class="fa-solid fa-rotate"></i>Neuer Zufall</button></div></div>`;
  document.querySelectorAll(".zeile").forEach((z) => z.classList.toggle("an", Number(z.dataset.nr) === nr));
}

function galerie(thema, fs) {
  document.title = "Nachschlag - Entwürfe Zufallsfunde";
  document.body.innerHTML = `<div class="entwurf">
    <div class="entwurf-kopf"><h1><i class="fa-solid fa-shuffle"></i> Zufallsfunde: acht Entwürfe</h1>
      <a class="chip" href="?thema=${thema === "dunkel" ? "hell" : "dunkel"}"><i class="fa-solid fa-circle-half-stroke"></i>${thema === "dunkel" ? "Hell" : "Dunkel"}</a></div>
    <p class="erklaerung">Ticket WIKI-89. Alle Entwürfe zeigen dieselben ${fs.length} echten Funde aus den Probebüchern (${fs.filter((f) => f.bild).length} mit Bild).
      Ohne Artikelbild steht das Symbol des Buchs freigestellt auf der Farbe seiner Art. Jede Variante geht anders mit der Flut an Karten um.</p>
    <div class="v-bildkarte">${VARIANTEN.map(([k, n, t], i) => `
      <a class="kachel hoch art-${fs[[11, 3, 6, 12, 7, 1, 8, 4][i]].art}" data-karte href="${k}.html?thema=${thema}">${titelbild(fs[[11, 3, 6, 12, 7, 1, 8, 4][i]])}
        <span class="kachel-koerper"><span class="kachel-titel">${e(n)}</span><span class="auszug" style="-webkit-line-clamp:5">${e(t)}</span></span></a>`).join("")}</div></div>`;
}

(async function () {
  const variante = document.body.dataset.variante;
  const thema = new URLSearchParams(location.search).get("thema") ?? "dunkel";
  document.documentElement.dataset.theme = thema;
  const fs = await (await fetch("daten/funde.json")).json();
  if (variante === "galerie") return galerie(thema, fs);
  const [, name, text] = VARIANTEN.find((v) => v[0] === variante);
  document.title = `Nachschlag - Zufallsfunde ${name}`;
  document.body.innerHTML = `<div class="entwurf">
    <div class="entwurf-kopf"><h1><i class="fa-solid fa-shuffle"></i> Stöbern · ${e(name)}</h1>
      <a class="chip" href="index.html"><i class="fa-solid fa-table-cells"></i>Alle Varianten</a>
      <a class="chip" href="?thema=${thema === "dunkel" ? "hell" : "dunkel"}"><i class="fa-solid fa-circle-half-stroke"></i>${thema === "dunkel" ? "Hell" : "Dunkel"}</a></div>
    <p class="erklaerung">${e(text)}</p>
    <div class="varianten">${VARIANTEN.map(([k, n]) => `<a class="chip wahl ${k === variante ? "an" : ""}" href="${k}.html?thema=${thema}">${e(n)}</a>`).join("")}</div>
    <div id="buehne"></div></div>`;
  const buehne = document.getElementById("buehne");
  const bauen = () => { buehne.innerHTML = BAUEN[variante](fs); if (variante === "pult") pultZeigen(fs, 0); };
  bauen();
  if (variante === "stapel") addEventListener("resize", bauen);
  if (variante === "pult") buehne.addEventListener("mouseover", (ev) => { const z = ev.target.closest(".zeile"); if (z) pultZeigen(fs, Number(z.dataset.nr)); });
})();
