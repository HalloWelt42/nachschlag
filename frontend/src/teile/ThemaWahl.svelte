<script lang="ts">
  // Knopf "Thema" im Artikelkopf: klappt die Themen des Kontos auf; ein Haken zeigt, wo der Artikel schon liegt, ein
  // Tipp legt ihn hinein oder nimmt ihn heraus. Unten ein neues Thema, in das er gleich kommt. Schließt bei Klick
  // daneben und mit Escape.
  import { seitenFehler } from "appkern-oberflaeche";
  import { austragen, eintragen, themaAnlegen, themen, themenLaden, themenVon, type Artikelangabe } from "../lib/themen.svelte";

  let { artikel, buchName }: { artikel: Artikelangabe; buchName: string } = $props();

  let offen = $state(false);
  let neu = $state("");
  let fehler = $state("");
  let arbeitet = $state(false);
  let wurzel: HTMLElement;

  const drin = $derived(themenVon(buchName, artikel.pfad));

  function umschalten() {
    offen = !offen;
    if (offen) void themenLaden();
  }

  async function tun(arbeit: () => Promise<unknown>) {
    arbeitet = true;
    try {
      await arbeit();
      fehler = "";
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      arbeitet = false;
    }
  }

  function wechseln(thema: string) {
    const z = drin.find((x) => x.thema === thema);
    void tun(() => (z ? austragen(thema, z.eintrag) : eintragen(thema, artikel)));
  }

  function anlegen() {
    const titel = neu.trim();
    if (!titel) return;
    neu = "";
    void tun(async () => eintragen((await themaAnlegen(titel)).id, artikel));
  }
</script>

<svelte:window onclick={(e) => offen && !wurzel.contains(e.target as Node) && (offen = false)}
               onkeydown={(e) => e.key === "Escape" && (offen = false)} />
<div class="thema-wahl" bind:this={wurzel}>
  <button class="knopf" class:an={drin.length > 0} title={drin.length ? `In ${drin.map((z) => z.titel).join(", ")}` : "In ein Thema legen"}
          aria-expanded={offen} onclick={umschalten}>
    <i class="fa-solid fa-layer-group"></i><span class="wort">Thema</span>{#if drin.length}<span class="zahl">{drin.length}</span>{/if}</button>
  {#if offen}
    <div class="thema-wahl-liste" role="menu">
      {#each themen.liste as t (t.id)}
        {@const an = drin.some((z) => z.thema === t.id)}
        <button role="menuitemcheckbox" aria-checked={an} class:an disabled={arbeitet} onclick={() => wechseln(t.id)}>
          <i class="fa-{an ? 'solid fa-square-check' : 'regular fa-square'}"></i><span>{t.titel}</span><span class="zahl">{t.eintraege}</span></button>
      {/each}
      <form onsubmit={(e) => { e.preventDefault(); anlegen(); }}>
        <input name="neu" class="eingabe" bind:value={neu} placeholder="Neues Thema" maxlength="120" aria-label="Neues Thema" />
        <button class="knopf" disabled={!neu.trim() || arbeitet} title="Thema anlegen und den Artikel hineinlegen"><i class="fa-solid fa-plus"></i></button>
      </form>
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    </div>
  {/if}
</div>
