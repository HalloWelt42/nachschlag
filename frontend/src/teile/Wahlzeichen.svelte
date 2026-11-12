<script lang="ts">
  // Zeichen einer Wahl zum An- und Abwählen (WIKI-103): ein größeres Feld ohne Haken, gewählt in der Akzentfarbe mit
  // einem Kern; die Zeile wird dafür nicht höher. Nur das Zeichen: den Zustand trägt der Knopf drumherum (aria-pressed).
  let { an }: { an: boolean } = $props();
</script>

<span class="wahlzeichen" class:an aria-hidden="true"></span>
