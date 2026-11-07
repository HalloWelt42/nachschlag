// Zeichnet die iFixit-Entwürfe (WIKI-64) aus den echten Daten in daten.js: Kopfdaten, Werkzeuge, Schritte. Nur für die
// Entwürfe, kein Teil der App. Markierungen der Zeilen: Hinweis (note), Vorsicht (caution), Erinnerung (reminder); die
// Farbpunkte (rot, orange, gelb ...) gehören zu den Markierungen in den Bildern.
(function () {
  const D = window.IFIXIT;
  const MARKE = {
    note: { symbol: "fa-circle-info", wort: "Hinweis" },
    caution: { symbol: "fa-triangle-exclamation", wort: "Vorsicht" },
    reminder: { symbol: "fa-thumbtack", wort: "Erinnerung" },
  };
  const FARBEN = new Set(["red", "orange", "yellow", "green", "blue", "light_blue", "violet", "pink", "black"]);
  const esc = (t) => String(t).replace(/[&<>"]/g, (z) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[z]);

  function stufe(schwierigkeit) {
    const n = Number((schwierigkeit || "").replace("difficulty-", "")) || 0;
    return `<span class="ifx-stufe" title="Schwierigkeit ${n} von 5">${[1, 2, 3, 4, 5].map((i) => `<span class="${i <= n ? "an" : ""}"></span>`).join("")}</span>`;
  }

  function zeile(z) {
    const m = MARKE[z.marke];
    const farbe = !m && FARBEN.has(z.farbe) && z.farbe !== "black" ? z.farbe : "";
    return `<li class="ifx-zeile stufe-${z.stufe}${m ? " marke-" + z.marke : ""}">` +
      (m ? `<i class="fa-solid ${m.symbol}" title="${m.wort}"></i>` : `<span class="ifx-punkt${farbe ? " f-" + farbe : ""}" title="${farbe ? "Markierung im Bild: " + farbe : ""}"></span>`) +
      `<span>${esc(z.text)}</span></li>`;
  }

  function schritt(s, gross) {
    const [haupt, ...weitere] = s.bilder;
    const bild = haupt ? `<figure class="ifx-bild"><img src="${haupt}" alt="" loading="lazy">` +
      (s.bilder.length > 1 ? `<div class="ifx-vorschau">${s.bilder.map((b, i) => `<img class="${i ? "" : "an"}" src="${b}" alt="">`).join("")}</div>` : "") +
      `</figure>` : `<figure class="ifx-bild leer"><i class="fa-regular fa-image"></i>Bild im Entwurf ausgelassen</figure>`;
    const titel = s.titel || `Schritt ${s.nr}`;          // die Quelle gibt Schritten selten einen Titel
    return `<section class="ifx-schritt${gross ? " gross" : ""}" id="schritt-${s.nr}">` +
      `<h2><span class="ifx-nr">${s.nr}</span>${esc(titel)}</h2>${bild}<ul class="ifx-zeilen">${s.zeilen.map(zeile).join("")}</ul></section>`;
  }

  window.ifx = {
    D, esc, stufe, zeile, schritt,
    schritte(ziel, von, bis) {
      ziel.innerHTML = D.anleitung.schritte.slice(von - 1, bis).map((s) => schritt(s)).join("");
    },
    werkzeuge(ziel, liste) {
      ziel.innerHTML = liste.map((w) => `<li>${w.bild ? `<img src="${w.bild}" alt="">` : '<span class="ohne"><i class="fa-solid fa-screwdriver-wrench"></i></span>'}<span>${esc(w.name)}</span></li>`).join("");
    },
  };
})();
