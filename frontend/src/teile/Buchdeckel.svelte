<script lang="ts">
  // Ein Buchdeckel (Entwurf export.html, Vorschau): Titelbild mit Titel und Untertitel darüber. Ohne Bild eine Fläche
  // in der Farbe der App.
  let { bild = "", titel, untertitel = "" }: { bild?: string; titel: string; untertitel?: string } = $props();
</script>

<div class="exp-titel" class:mit-bild={!!bild}>
  {#if bild}<img src={bild} alt="" loading="lazy" />{/if}
  <span><b>{titel}</b>{#if untertitel}<small>{untertitel}</small>{/if}</span>
</div>
