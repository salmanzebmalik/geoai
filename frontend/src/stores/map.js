import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMapStore = defineStore('map', () => {
  // === Map state ===
  const mapType = ref('orthophoto') // default map type
  const mapCenter = ref([7.6261, 51.9607]) // default Münster coordinates
  const mapZoom = ref(13.5) // default zoom level

  // === User selection ===
  const bbox = ref(null)
  const areaSqm = ref(null)
  
  const selectedTask = ref('Tree Detection')
  const modelType = ref('tree')  // 'tree' or 'zeroshot'
  const keyword = ref('house')    // For zeroshot model

  const hasPrediction = ref(false) // whether the prediction overlay currently has polygons shown on the map

  const historyDrawerOpen = ref(false) // whether the prediction history drawer is open

  // triggers
  const startDrawingTrigger = ref(0)
  const runTrigger = ref(0)
  
  const isPredicting = ref(false) // for loading display

  const viewedPrediction = ref(null) // geojson of a past prediction selected in the history drawer

  const errorMessage = ref(null) // error handling

  // User selection
  function setMapType(type) {
    mapType.value = type
  }

  function setModelType(type) {
    modelType.value = type
  }

  function setKeyword(text) {
    keyword.value = text
  }

  // Set triggers
  function triggerDrawing() {
    startDrawingTrigger.value++ // jedes Increment = neues Zeichnen
  }  

  function triggerRun() {
    runTrigger.value++
  }

  // set geojson of pas prediction
  function setViewedPrediction(geojson) {
    viewedPrediction.value = geojson
  }

  // error handling
  function setError(msg) {
    errorMessage.value = msg
  }

  function clearError() {
    errorMessage.value = null
  }
  

  return {
    startDrawingTrigger, triggerDrawing, mapType, setMapType, mapCenter, mapZoom, bbox, runTrigger, triggerRun, selectedTask, areaSqm, isPredicting,
    modelType, keyword,  setModelType, setKeyword,
    viewedPrediction, setViewedPrediction,
    hasPrediction,
    historyDrawerOpen,
    errorMessage, setError, clearError,
  }
})