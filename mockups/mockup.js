// Gemeinsames Skript der Entwürfe: setzt den geteilten Artikel ein, die Suchvorschläge und die Leiste unten rechts
// (Thema, Lesegröße, Suche offen). Nur für die Entwürfe, kein Teil der App.
(async function () {
  const wurzel = document.documentElement;
  const ziele = document.querySelectorAll("[data-artikel]");
  if (ziele.length) {
    const html = await (await fetch("teile/artikel.html")).text();
    ziele.forEach((ziel) => { ziel.innerHTML = html; });
  }
  // Gemeinsame Teile der Schale (Kopf, Seitenleiste, Fuß); data-teil="nav:einstellungen" setzt den aktiven Eintrag
  for (const platz of document.querySelectorAll("[data-teil]")) {
    const [teil, aktiv] = platz.dataset.teil.split(":");
    platz.outerHTML = (await (await fetch(`teile/${teil}.html`)).text())
      .replace(`data-ziel="${aktiv}"`, `data-ziel="${aktiv}" aria-current="page"`);
  }
  document.querySelectorAll('.nav-eintrag[aria-current="page"]').forEach((a) => a.classList.add("aktiv"));
  const sucheZiel = document.querySelectorAll("[data-vorschlaege]");
  if (sucheZiel.length) {
    const html = await (await fetch("teile/vorschlaege.html")).text();
    sucheZiel.forEach((ziel) => { ziel.innerHTML = html; });
  }
  // Zustände je Seite: Fundstelle, vorgelesener Absatz, Steckbrief in die Leiste
  const fund = document.body.dataset.fundstelle;
  if (fund) document.querySelectorAll(`[data-absatz="${fund}"]`).forEach((p) => p.classList.add("fundstelle"));
  const liest = document.body.dataset.liest;
  if (liest) document.querySelectorAll(`[data-absatz="${liest}"]`).forEach((p) => {
    p.classList.add("liest");
    p.innerHTML = p.innerHTML.replace("Körpergewicht", '<span class="liest-wort">Körpergewicht</span>');
  });
  const steckbriefZiel = document.querySelector("[data-steckbrief-ziel]");
  const steckbrief = document.querySelector(".artikel .steckbrief");
  if (steckbriefZiel && steckbrief) steckbriefZiel.appendChild(steckbrief.cloneNode(true));

  const leiste = document.createElement("div");
  leiste.className = "mock-leiste";
  // Ansicht A, B, C umschalten (in der App frei wählbar); Zustände der Leiste gehen mit
  const gruppen = [[["artikel-a.html", "A"], ["artikel-b.html", "B"], ["artikel-c.html", "C"]], [["start-a.html", "A"], ["start-b.html", "B"]]];
  const hier = location.pathname.split("/").pop();
  const ansichten = gruppen.find((g) => g.some(([d]) => d === hier)) ?? [];
  const wahl = ansichten.some(([d]) => d === hier)
    ? ansichten.map(([d, n]) => `<a href="${d}${location.search}" class="${d === hier ? "an" : ""}">${n}</a>`).join("") : "";
  leiste.innerHTML = '<a href="index.html">Galerie</a>' + wahl + '<button data-k="thema">Dunkel</button><button data-k="groesse">Lesegröße groß</button>' +
    (document.querySelector(".suchanker") ? '<button data-k="suche">Suche offen</button>' : "");
  document.body.appendChild(leiste);
  const params = new URLSearchParams(location.search);
  const setze = (k, an) => {
    if (k === "thema") wurzel.dataset.theme = an ? "dunkel" : "hell";
    if (k === "groesse") wurzel.dataset.lesegroesse = an ? "gross" : "";
    if (k === "suche") document.querySelectorAll(".suchanker").forEach((s) => s.classList.toggle("offen", an));
    leiste.querySelector(`[data-k="${k}"]`)?.classList.toggle("an", an);
  };
  ["thema", "groesse", "suche"].forEach((k) => { if (params.get(k)) setze(k, true); });
  if (params.get("bild")) document.body.classList.add("bild-offen");
  if (params.get("nurindex")) document.body.classList.add("nur-index");
  leiste.addEventListener("click", (e) => {
    const k = e.target.dataset.k;
    if (k) setze(k, !e.target.classList.contains("an"));
  });
})();
