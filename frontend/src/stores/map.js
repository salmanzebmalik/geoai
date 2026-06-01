import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMapStore = defineStore('map', () => {
  const startDrawingTrigger = ref(0)

  const mapType = ref('sentinel')

  const mapCenter = ref([7.6261, 51.9607]) // default Münster coordinates
  const mapZoom = ref(13.5) // default zoom level

  function triggerDrawing() {
    startDrawingTrigger.value++ // jedes Increment = neues Zeichnen
  }

  function setMapType(type) {
    mapType.value = type
  }

  return { startDrawingTrigger, triggerDrawing, mapType, setMapType, mapCenter, mapZoom }
})