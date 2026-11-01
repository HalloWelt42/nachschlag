// Namen aus dem Code erkennen (Handbücher): eine Stelle für Artikel, Übersichten und Suchtreffer.

/** Ein Eintrag ist ein Name aus dem Code (Funktion, Klasse, Methode), wenn er Zeichen aus dem Code trägt, klein
 *  beginnt (basename) oder Binnengroßbuchstaben hat (ArrayObject); nur dann steht er in der Schrift des Editors.
 *  Kapitelnamen ("Getting Started", "Types") bleiben Text. */
export function istCode(titel: string): boolean {
  const name = titel.replace(/\s*\((class|interface|enum|trait)\)$/, "");
  if (/\s/.test(name)) return false;
  return /[_$\\]|::|->|\(\)$/.test(name) || /^[a-z]/.test(name) || /[a-z][A-Z]/.test(name);
}
