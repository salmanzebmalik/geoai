<template>
  <v-btn
    icon="mdi-history"
    class="history-toggle"
    :class="{ 'history-toggle--shifted': mapStore.historyDrawerOpen }"
    color="success"
    @click="toggleDrawer"
  />

  <v-navigation-drawer
    v-model="mapStore.historyDrawerOpen"
    location="end"
    temporary
    width="340"
  >
    <div class="drawer-header">
      <span class="drawer-title">Prediction History</span>
      <v-btn
        icon="mdi-refresh"
        variant="text"
        size="small"
        :loading="loading"
        @click="loadHistory"
      />
    </div>

    <v-divider />

    <div v-if="error" class="drawer-message error-message">{{ error }}</div>
    <div v-else-if="!loading && history.length === 0" class="drawer-message">
      No predictions yet.
    </div>

    <v-list lines="two">
      <v-list-item
        v-for="item in history"
        :key="item.query_id"
        class="history-item"
        :disabled="viewingId === item.query_id"
        @click="viewPrediction(item)"
      >
        <template #title>
          <span class="item-title">{{ formatLabel(item) }}</span>
        </template>

        <template #subtitle>
          <span>{{ formatDate(item.created_at) }}</span>
        </template>

        <template #append>
          <v-btn
            icon="mdi-download"
            variant="text"
            size="small"
            :loading="downloadingId === item.query_id"
            @click.stop="downloadPrediction(item)"
          />
        </template>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { ref } from 'vue'
import { useMapStore } from '@/stores/map'

const API_BASE_URL = '/api/segmentation'

const mapStore = useMapStore()

const history = ref([])
const loading = ref(false)
const error = ref(null)
const downloadingId = ref(null)
const viewingId = ref(null)

function toggleDrawer() {
  mapStore.historyDrawerOpen = !mapStore.historyDrawerOpen

  if (mapStore.historyDrawerOpen && history.value.length === 0) {
    loadHistory()
  }
}

async function loadHistory() {
  loading.value = true
  error.value = null

  try {
    const response = await fetch(`${API_BASE_URL}/results`)

    if (!response.ok) {
      throw new Error('Failed to fetch prediction history')
    }

    history.value = await response.json()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function formatLabel(item) {
  if (!item.prediction_type) return 'Prediction'
  return item.prediction_type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleString()
}

async function fetchResultById(queryId) {
  const response = await fetch(`${API_BASE_URL}/results/${queryId}`)

  if (!response.ok) {
    throw new Error('Failed to fetch prediction result')
  }

  return response.json()
}

async function fetchGeoJSONResponse(result) {
  const resultUrl = result.prediction?.result_url

  if (!resultUrl) {
    throw new Error(
      'This prediction has no stored result file'
    )
  }

  let response

  try {
    response = await fetch(resultUrl)
  } catch {
    throw new Error(
      'The stored prediction file could not be reached'
    )
  }

  if (!response.ok) {
    throw new Error(
      'Failed to fetch prediction GeoJSON'
    )
  }

  return response
}

async function downloadPrediction(item) {
  downloadingId.value = item.query_id

  try {
    const result = await fetchResultById(item.query_id)

    const geojsonResponse = await fetchGeoJSONResponse(
      result
    )

    const blob = await geojsonResponse.blob()
    const url = URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = url
    link.download = `prediction_${item.query_id}.geojson`
    document.body.appendChild(link)
    link.click()
    link.remove()

    URL.revokeObjectURL(url)
  } catch (err) {
    error.value = err.message
  } finally {
    downloadingId.value = null
  }
}

async function viewPrediction(item) {
  if (viewingId.value) return

  viewingId.value = item.query_id

  try {
    const result = await fetchResultById(item.query_id)

    const geojsonResponse = await fetchGeoJSONResponse(
      result
    )

    const geojson = await geojsonResponse.json()

    mapStore.setViewedPrediction(geojson)
    mapStore.historyDrawerOpen = false
  } catch (err) {
    error.value = err.message
  } finally {
    viewingId.value = null
  }
}
</script>

<style scoped>
.history-toggle {
  position: fixed;
  top: 84px;
  right: 16px;
  z-index: 1005;
  transition: right 0.2s ease;
}

.history-toggle--shifted {
  right: 356px;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
}

.drawer-title {
  font-weight: 600;
}

.drawer-message {
  padding: 16px;
  color: rgba(0, 0, 0, 0.6);
  font-size: 13px;
}

.error-message {
  color: #b00020;
}

.item-title {
  font-weight: 500;
}

.history-item {
  cursor: pointer;
}
</style>
