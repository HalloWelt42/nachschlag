// Brücke der Originalansicht von Nachschlag (WIKI-85). Läuft in jeder Originalseite auf der eigenen Herkunft der Bücher
// und ändert nichts an ihrem Aussehen:
//  - meldet der App, welche Seite des Buchs offen ist (beim Laden, nach dem Zurückholen aus dem Verlauf, bei einem neuen
//    Anker), damit Adresse und Verlauf der App stimmen, auch wenn die Seite selbst weitergeht
//  - reicht einen Verweis auf eine andere Seite des Buchs an die App weiter; sie öffnet ihn im Lesen (mit eigenem
//    Lesedesign, wenn sie die Seite selbst aufbereitet)
//  - öffnet Verweise nach außen in einem neuen Tab (im Rahmen zeigen sich fremde Seiten ohnehin nicht)
//  - nimmt die Lesegröße der App an
// Nachrichten tragen nur den Ort im Buch (Buch, Pfad, Abfrage, Anker), nie den Schein aus der Adresse. Hat eine Seite
// einen Klick selbst behandelt, bleibt er bei ihr.
(() => {
  "use strict";
  if (window.parent === window) return;                          // allein geöffnet: keine App, nichts zu verbinden
  const teile = location.pathname.split("/");                    // "", api, v1, original, <schein>, <buch>, ...
  const wurzel = `${teile.slice(0, 5).join("/")}/`;
  const buch = `${wurzel}${teile[5]}/`;
  const ort = (u) => u.pathname.slice(wurzel.length) + u.search + u.hash;
  const melden = (art, wert) => window.parent.postMessage({ nachschlag: 1, art, ort: wert }, "*");

  melden("ort", ort(location));
  addEventListener("pageshow", (e) => { if (e.persisted) melden("ort", ort(location)); });
  addEventListener("hashchange", () => melden("ort", ort(location)));

  addEventListener("message", (e) => {
    const d = e.data;
    if (e.source !== window.parent || !d || d.nachschlag !== 1) return;
    if (d.art === "zoom") document.documentElement.style.zoom = String(d.wert);
  });

  addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    const a = e.target instanceof Element ? e.target.closest("a[href]") : null;
    if (!a || a.hasAttribute("download") || (a.target && a.target !== "_self")) return;
    let u;
    try { u = new URL(a.getAttribute("href"), document.baseURI); } catch { return; }
    if (u.origin === location.origin) {
      if (!u.pathname.startsWith(buch) || (u.pathname === location.pathname && u.search === location.search)) return;
      e.preventDefault();
      melden("verweis", ort(u));
    } else if (u.protocol === "http:" || u.protocol === "https:") {
      e.preventDefault();
      window.open(u.href, "_blank", "noopener,noreferrer");
    }
  });
})();
