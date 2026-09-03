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
  
  const rasterEstimate = ref(null)
  const rasterEstimateError = ref(null)
  const isEstimatingRaster = ref(false)

  const selectedTask = ref('Tree Detection')
  const modelType = ref('tree')  // 'tree' or 'zeroshot'
  const modelVariant = ref('sam2.1_hiera_large')
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
  const viewedQueryId = ref(null)
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
  const errorTitle = ref('Something went wrong')
  const errorKind = ref('error')

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

  function setViewedPrediction(
    geojson,
    queryId = null,
    meta = null,
  ) {
    viewedPrediction.value = geojson
    viewedQueryId.value = queryId
    viewedPredictionMeta.value = meta

    if (queryId) {
      currentQueryId.value = queryId
    }
  }

  function setCurrentPrediction(
    queryId,
    geojson = null,
    meta = null,
  ) {
    currentQueryId.value = queryId

    if (geojson) {
      viewedPrediction.value = geojson
      viewedQueryId.value = queryId
    }

    if (meta) {
      viewedPredictionMeta.value = meta
    }
  }

  function clearPredictionForQuery(queryId) {
    if (viewedQueryId.value === queryId) {
      viewedPrediction.value = null
      viewedQueryId.value = null
      viewedPredictionMeta.value = null
      hasPrediction.value = false
    }

    if (currentQueryId.value === queryId) {
      currentQueryId.value = null
      currentExport.value = null
    }
  }

  function setCurrentExport(value) {
    currentExport.value = value
  }

  function setError(message, options = {}) {
    errorMessage.value = message
    errorTitle.value = options.title ?? 'Something went wrong'
    errorKind.value = options.kind ?? 'error'
  }

  function clearError() {
    errorMessage.value = null
    errorTitle.value = 'Something went wrong'
    errorKind.value = 'error'
  }
  
  function clearRasterEstimate() {
    rasterEstimate.value = null
    rasterEstimateError.value = null
    isEstimatingRaster.value = false
  }

  return {
    mapType, setMapType, mapCenter, mapZoom,
    bbox, areaSqm,
    rasterEstimate, rasterEstimateError, isEstimatingRaster,
    clearRasterEstimate,
    selectedTask, modelType, modelVariant, keyword, setModelType, setKeyword,
    sentinelDateFrom, sentinelDateTo, sentinelMaxCloudCover,
    hasPrediction, viewedPrediction, viewedPredictionMeta, viewedQueryId,
    currentQueryId, currentExport, isPredicting, isExporting,
    historyDrawerOpen, coordinateInputOpen,
    startDrawingTrigger, triggerDrawing,
    runTrigger, triggerRun,
    manualBboxTrigger, triggerManualBboxUpdate,
    sentinelRefreshTrigger, triggerSentinelRefresh,
    exportDialogTrigger, openExportDialog,
    setViewedPrediction, setCurrentPrediction, clearPredictionForQuery, setCurrentExport,
    errorMessage, setError, clearError, errorTitle, errorKind
  }
})
