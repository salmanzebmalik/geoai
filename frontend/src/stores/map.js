import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMapStore = defineStore('map', () => {
  const startDrawingTrigger = ref(0)

  const mapType = ref('sentinel')

  function triggerDrawing() {
    startDrawingTrigger.value++ // jedes Increment = neues Zeichnen
  }

  function setMapType(type) {
    mapType.value = type
  }

  return { startDrawingTrigger, triggerDrawing, mapType, setMapType }
})