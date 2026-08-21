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

  // === Sentinel STAC search filters ===
  const sentinelDateFrom = ref('2024-04-01') // growing season: avoids snow, and wide enough that every tile has a scene
  const sentinelDateTo = ref('2024-09-30')
  const sentinelMaxCloudCover = ref(25) // percent, 0-100

  const coordinateInputOpen = ref(false) // whether the manual coordinate input overlay is open

  // triggers
  const manualBboxTrigger = ref(0)
  const sentinelRefreshTrigger = ref(0) // date range / cloud cover filter changed
  
  // Prediction and export state
  const hasPrediction = ref(false)
  const viewedPrediction = ref(null)
  const viewedPredictionMeta = ref(null)
  const currentQueryId = ref(null)
  const currentExport = ref(null)
  const isPredicting = ref(false)
  const isExporting = ref(false)

  // UI state and triggers
  const historyDrawerOpen = ref(false)
  const startDrawingTrigger = ref(0)
  const runTrigger = ref(0)
  const exportDialogTrigger = ref(0)
  const errorMessage = ref(null)

  function setMapType(type) {
    mapType.value = type
  }

  function setModelType(type) {
    modelType.value = type
  }

  function setKeyword(text) {
    keyword.value = text
  }

  function triggerDrawing() {
    startDrawingTrigger.value++
  }

  function triggerRun() {
    runTrigger.value++
  }

  function triggerManualBboxUpdate() {
    manualBboxTrigger.value++ // tells Map.vue to redraw the box after a manual coordinate entry
  }

  function triggerSentinelRefresh() {
    sentinelRefreshTrigger.value++ // tells Map.vue to re-register the STAC search
  }

  function openExportDialog() {
    exportDialogTrigger.value++
  }

  function setViewedPrediction(geojson, queryId = null, meta = null) {
    viewedPrediction.value = geojson
    viewedPredictionMeta.value = meta
    if (queryId) currentQueryId.value = queryId
  }

  function setCurrentPrediction(queryId, geojson = null, meta = null) {
    currentQueryId.value = queryId
    if (geojson) viewedPrediction.value = geojson
    if (meta) viewedPredictionMeta.value = meta
  }

  function setCurrentExport(value) {
    currentExport.value = value
  }

  function setError(message) {
    errorMessage.value = message
  }

  function clearError() {
    errorMessage.value = null
  }

  return {
    mapType, setMapType, mapCenter, mapZoom,
    bbox, areaSqm, selectedTask, modelType, keyword, setModelType, setKeyword,
    sentinelDateFrom, sentinelDateTo, sentinelMaxCloudCover,
    hasPrediction, viewedPrediction, viewedPredictionMeta, currentQueryId, currentExport, isPredicting, isExporting,
    historyDrawerOpen, coordinateInputOpen,
    startDrawingTrigger, triggerDrawing,
    runTrigger, triggerRun,
    manualBboxTrigger, triggerManualBboxUpdate,
    sentinelRefreshTrigger, triggerSentinelRefresh,
    exportDialogTrigger, openExportDialog,
    setViewedPrediction, setCurrentPrediction, setCurrentExport,
    errorMessage, setError, clearError,
  }
})
