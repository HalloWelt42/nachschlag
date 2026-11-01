/** In die Zwischenablage; ohne sicheren Zusammenhang (http im Heimnetz) über ein Textfeld im Klick. */
export async function kopieren(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const feld = document.createElement("textarea");
    feld.value = text;
    document.body.append(feld);
    feld.select();
    document.execCommand("copy");
    feld.remove();
  }
}
