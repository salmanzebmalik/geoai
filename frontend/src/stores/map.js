import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMapStore = defineStore('map', () => {
  const startDrawingTrigger = ref(0)

  const mapType = ref('orthophoto') // default map type

  const selectedTask = ref('Tree Detection')

  const mapCenter = ref([7.6261, 51.9607]) // default Münster coordinates
  const mapZoom = ref(13.5) // default zoom level

  const bbox = ref(null)
  const runTrigger = ref(0)
  const isPredicting = ref(false)

  const areaSqm = ref(null)

  const modelType = ref('tree')  // 'tree' or 'zeroshot'
  const keyword = ref('house')    // For zeroshot model

  const errorMessage = ref(null)

  function setError(msg) {
    errorMessage.value = msg
  }

  function clearError() {
    errorMessage.value = null
  }

  function triggerDrawing() {
    startDrawingTrigger.value++ // jedes Increment = neues Zeichnen
  }

  function setMapType(type) {
    mapType.value = type
  }

  function triggerRun() {
    runTrigger.value++
  }

  // 
  function setModelType(type) {
    modelType.value = type
  }

  function setKeyword(text) {
    keyword.value = text
  }


  return {
    startDrawingTrigger, triggerDrawing, mapType, setMapType, mapCenter, mapZoom, bbox, runTrigger, triggerRun, selectedTask, areaSqm, isPredicting,
    modelType, keyword, setModelType, setKeyword,
    errorMessage, setError, clearError,
  }
})