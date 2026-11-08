<script lang="ts">
  // Bild, das sich vergrößern lässt (WIKI-69): zwei Finger ziehen auf und zu, Doppeltippen (Doppelklick) springt auf
  // die doppelte Größe an der Stelle und zurück, vergrößert verschiebt ein Finger (die Maus) das Bild, das Mausrad
  // vergrößert am Zeiger. Unvergrößert gehören Wischen und Tippen dem Rahmen (Blättern); `vergroessert` meldet das.
  // Klassen mit zb-.
  let { src, alt = "", vergroessert = $bindable(false) }: { src: string; alt?: string; vergroessert?: boolean } = $props();

  const HOECHSTENS = 6;
  const DOPPELT = 2.5;
  const DOPPELTIPP_MS = 300;

  let feld = $state<HTMLDivElement>();
  let massstab = $state(1);
  let x = $state(0);
  let y = $state(0);

  // bei jedem neuen Bild wieder eingepasst
  $effect(() => {
    void src;
    zuruecksetzen();
  });
  $effect(() => {
    vergroessert = massstab > 1.01;
  });

  function zuruecksetzen() {
    massstab = 1;
    x = 0;
    y = 0;
  }

  /** Auf `neu` vergrößern, so dass der Punkt (px, py) relativ zur Mitte des Felds stehen bleibt. */
  function zoomen(neu: number, px: number, py: number) {
    neu = Math.min(Math.max(neu, 1), HOECHSTENS);
    if (neu === 1) return zuruecksetzen();
    const f = neu / massstab;
    x = px - (px - x) * f;
    y = py - (py - y) * f;
    massstab = neu;
    begrenzen();
  }

  /** Das Bild nie ganz aus dem Feld schieben. */
  function begrenzen() {
    if (!feld) return;
    const randX = (feld.clientWidth * (massstab - 1)) / 2, randY = (feld.clientHeight * (massstab - 1)) / 2;
    x = Math.min(Math.max(x, -randX), randX);
    y = Math.min(Math.max(y, -randY), randY);
  }

  function relativ(e: { clientX: number; clientY: number }): [number, number] {
    const r = feld!.getBoundingClientRect();
    return [e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2];
  }

  // Finger und Maus: zwei Zeiger ziehen auf und zu, einer verschiebt (nur vergrößert)
  const zeiger = new Map<number, { x: number; y: number }>();
  let abstand = 0;
  let letzterTipp = 0;

  function runter(e: PointerEvent) {
    zeiger.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (zeiger.size === 2) {
      const [a, b] = [...zeiger.values()];
      abstand = Math.hypot(a.x - b.x, a.y - b.y);
    }
    if (vergroessert || zeiger.size === 2) {
      feld?.setPointerCapture(e.pointerId);
      e.stopPropagation();                         // der Rahmen blättert nicht, solange gezoomt wird
    }
  }

  function ziehen(e: PointerEvent) {
    const alt = zeiger.get(e.pointerId);
    if (!alt) return;
    zeiger.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (zeiger.size === 2) {
      const [a, b] = [...zeiger.values()];
      const neu = Math.hypot(a.x - b.x, a.y - b.y);
      if (abstand > 0) zoomen(massstab * (neu / abstand), ...relativ({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 }));
      abstand = neu;
    } else if (vergroessert) {
      x += e.clientX - alt.x;
      y += e.clientY - alt.y;
      begrenzen();
    }
  }

  function hoch(e: PointerEvent) {
    const war = zeiger.size;
    zeiger.delete(e.pointerId);
    if (zeiger.size < 2) abstand = 0;
    if (vergroessert || war === 2) e.stopPropagation();
  }

  function tippen(e: MouseEvent) {
    const jetzt = Date.now();
    if (jetzt - letzterTipp < DOPPELTIPP_MS) {
      letzterTipp = 0;
      if (vergroessert) zuruecksetzen();
      else zoomen(DOPPELT, ...relativ(e));
      e.stopPropagation();
      return;
    }
    letzterTipp = jetzt;
    if (vergroessert) e.stopPropagation();
  }

  function rad(e: WheelEvent) {
    e.preventDefault();
    zoomen(massstab * (e.deltaY < 0 ? 1.15 : 1 / 1.15), ...relativ(e));
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
<div class="zb-feld" class:zb-gross={vergroessert} bind:this={feld} onpointerdown={runter} onpointermove={ziehen} onpointerup={hoch}
     onpointercancel={hoch} onclick={tippen} onwheel={rad}>
  <img {src} {alt} draggable="false" style:transform="translate({x}px, {y}px) scale({massstab})" />
</div>
