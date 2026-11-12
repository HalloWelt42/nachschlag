<script lang="ts" module>
  /** Ein Punkt des Menüs: Zeichen (Font Awesome, etwa fa-volume-high), Wort und was er tut. */
  export interface Menuepunkt {
    symbol: string;
    titel: string;
    aktion: () => void;
  }
</script>

<script lang="ts">
  // Eigenes Menü per Rechtsklick (WIKI-107): steht an der Stelle des Klicks und bleibt im Fenster; Escape, ein Klick
  // daneben, Rollen oder eine andere Fenstergröße schließen es. Ein Punkt schließt das Menü, dann tut er seine Arbeit
  // (noch im Tippen: Vorlesen braucht das am iPhone). Mit den Pfeiltasten wählbar.
  import { onMount, tick } from "svelte";

  let { x, y, titel = "", punkte, onzu }: { x: number; y: number; titel?: string; punkte: Menuepunkt[]; onzu: () => void } = $props();

  const RAND = 8;
  let el: HTMLElement;
  let links = $state(0);
  let oben = $state(0);

  onMount(() => {
    const r = el.getBoundingClientRect();
    links = Math.max(RAND, Math.min(x, innerWidth - r.width - RAND));
    oben = Math.max(RAND, Math.min(y, innerHeight - r.height - RAND));
    void tick().then(() => el.querySelector<HTMLButtonElement>("button")?.focus());
    const zu = () => onzu();
    addEventListener("scroll", zu, true);                 // auch das Rollen eines inneren Rollfelds
    return () => removeEventListener("scroll", zu, true);
  });

  function tasten(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onzu();
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const knoepfe = [...el.querySelectorAll<HTMLButtonElement>("button")];
      const i = knoepfe.indexOf(document.activeElement as HTMLButtonElement);
      knoepfe[(i + (e.key === "ArrowDown" ? 1 : -1) + knoepfe.length) % knoepfe.length]?.focus();
    }
  }

  function waehlen(p: Menuepunkt) {
    onzu();
    p.aktion();
  }
</script>

<svelte:window onkeydown={tasten} onresize={onzu} onpointerdown={(e) => !el.contains(e.target as Node) && onzu()} />
<div class="kontextmenue" role="menu" tabindex="-1" aria-label={titel || "Menü"} bind:this={el}
     style:left="{links}px" style:top="{oben}px" oncontextmenu={(e) => e.preventDefault()}>
  {#if titel}<div class="kontextmenue-titel">{titel}</div>{/if}
  {#each punkte as p (p.titel)}
    <button role="menuitem" onclick={() => waehlen(p)}><i class="fa-solid {p.symbol}"></i>{p.titel}</button>
  {/each}
</div>
