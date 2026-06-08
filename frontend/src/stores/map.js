import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMapStore = defineStore('map', () => {
  const startDrawingTrigger = ref(0)

  const mapType = ref('osm') // default map type

  const mapCenter = ref([7.6261, 51.9607]) // default Münster coordinates
  const mapZoom = ref(13.5) // default zoom level

  const bbox = ref(null)
  const runTrigger = ref(0)

  function triggerDrawing() {
    startDrawingTrigger.value++ // jedes Increment = neues Zeichnen
  }

  function setMapType(type) {
    mapType.value = type
  }

  function triggerRun() {
    runTrigger.value++
  }

  return { startDrawingTrigger, triggerDrawing, mapType, setMapType, mapCenter, mapZoom, bbox, runTrigger, triggerRun }
})