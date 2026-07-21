import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMapStore = defineStore('map', () => {
  // Map state
  const mapType = ref('orthophoto')
  const mapCenter = ref([7.6261, 51.9607])
  const mapZoom = ref(13.5)

  // User selection
  const bbox = ref(null)
  const areaSqm = ref(null)
  const selectedTask = ref('Tree Detection')
  const modelType = ref('tree')
  const keyword = ref('house')

  // Prediction and export state
  const hasPrediction = ref(false)
  const viewedPrediction = ref(null)
  const currentQueryId = ref(null)
  const currentExport = ref(null)
  const isPredicting = ref(false)
  const isExporting = ref(false)

  // UI state and triggers
  const historyDrawerOpen = ref(false)
  const startDrawingTrigger = ref(0)
  const runTrigger = ref(0)
  const exportDialogTrigger = ref(0)
  const detailsDialogTrigger = ref(0)
  const currentDetailsItem = ref(null)
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

  function openExportDialog() {
    exportDialogTrigger.value++
  }

  function openDetailsDialog(item) {
    currentDetailsItem.value = item
    detailsDialogTrigger.value++
  }

  function setViewedPrediction(geojson, queryId = null) {
    viewedPrediction.value = geojson
    if (queryId) currentQueryId.value = queryId
  }

  function setCurrentPrediction(queryId, geojson = null) {
    currentQueryId.value = queryId
    if (geojson) viewedPrediction.value = geojson
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
    mapType,
    mapCenter,
    mapZoom,
    bbox,
    areaSqm,
    selectedTask,
    modelType,
    keyword,
    hasPrediction,
    viewedPrediction,
    currentQueryId,
    currentExport,
    isPredicting,
    isExporting,
    historyDrawerOpen,
    startDrawingTrigger,
    runTrigger,
    exportDialogTrigger,
    detailsDialogTrigger,
    currentDetailsItem,
    errorMessage,
    setMapType,
    setModelType,
    setKeyword,
    triggerDrawing,
    triggerRun,
    openExportDialog,
    openDetailsDialog,
    setViewedPrediction,
    setCurrentPrediction,
    setCurrentExport,
    setError,
    clearError,
  }
})
