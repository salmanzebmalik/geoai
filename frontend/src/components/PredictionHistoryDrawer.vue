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
      <template v-for="item in history" :key="item.query_id">
        <v-list-item
          class="history-item"
          :disabled="
            viewingId === item.query_id ||
            deletingId === item.query_id
          "
          @click="viewPrediction(item)"
        >
          <template #title>
            <span class="item-title">{{ formatLabel(item) }}</span>
          </template>

          <template #subtitle>
            <span class="item-subtitle">
              <span class="item-date">{{ formatDate(item.created_at) }}</span>
              <v-chip
                v-if="isZeroShot(item)"
                size="x-small"
                variant="tonal"
                color="success"
                class="keyword-chip"
              >{{ resolveKeyword(item) || 'Unknown' }}</v-chip>
            </span>
          </template>

          <template #append>
            <v-btn
              icon="mdi-information-outline"
              variant="text"
              size="small"
              @click.stop="toggleDetails(item)"
            />
            <v-btn
              icon="mdi-tray-arrow-down"
              variant="text"
              size="small"
              @click.stop="exportPrediction(item)"
            />
            <v-btn
              icon="mdi-delete-outline"
              color="error"
              variant="text"
              size="small"
              title="Delete prediction"
              aria-label="Delete prediction"
              :loading="deletingId === item.query_id"
              :disabled="
                Boolean(viewingId) ||
                (
                  Boolean(deletingId) &&
                  deletingId !== item.query_id
                )
              "
              @click.stop="openDeleteDialog(item)"
            />
          </template>
        </v-list-item>

        <v-expand-transition>
          <div v-if="expandedId === item.query_id" class="details-panel">
            <div class="detail-row">
              <span class="detail-label">Prediction ID</span>
              <span class="detail-value">{{ item.query_id }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Model</span>
              <v-chip size="small" variant="tonal" color="secondary">{{ item.model_name || 'Unknown' }}</v-chip>
            </div>
            <div v-if="isZeroShot(item)" class="detail-row">
              <span class="detail-label">Keyword</span>
              <v-chip size="small" variant="tonal" color="success">{{ resolveKeyword(item) || 'Unknown' }}</v-chip>
            </div>
            <div class="detail-row">
              <span class="detail-label">Coordinates</span>
              <div class="bbox-coords">
                <span>N {{ item.bbox.max_lat.toFixed(5) }}</span>
                <span>S {{ item.bbox.min_lat.toFixed(5) }}</span>
                <span>E {{ item.bbox.max_lon.toFixed(5) }}</span>
                <span>W {{ item.bbox.min_lon.toFixed(5) }}</span>
              </div>
            </div>
            <div class="detail-row">
              <span class="detail-label">Area</span>
              <span class="detail-value">{{ formatArea(computeBboxArea(item.bbox)) }}</span>
            </div>
          </div>
        </v-expand-transition>
      </template>
    </v-list>
  </v-navigation-drawer>
  <v-dialog
    v-model="deleteDialogOpen"
    max-width="440"
    persistent
  >
    <v-card>
      <v-card-title>
        Delete prediction?
      </v-card-title>

      <v-card-text>
        <p>
          This permanently deletes the prediction record and
          all associated TIFF, GeoJSON and export files.
          This action cannot be undone.
        </p>

        <div
          v-if="pendingDelete"
          class="delete-summary"
        >
          <strong>{{ formatLabel(pendingDelete) }}</strong>
          <span>
            {{ formatDate(pendingDelete.created_at) }}
          </span>
          <span class="delete-query-id">
            {{ pendingDelete.query_id }}
          </span>
        </div>

        <v-alert
          v-if="deleteError"
          type="error"
          variant="tonal"
          class="mt-4"
        >
          {{ deleteError }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer />

        <v-btn
          variant="text"
          :disabled="Boolean(deletingId)"
          @click="closeDeleteDialog"
        >
          Cancel
        </v-btn>

        <v-btn
          color="error"
          variant="flat"
          prepend-icon="mdi-delete"
          :loading="Boolean(deletingId)"
          @click="confirmDelete"
        >
          Delete permanently
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-snackbar
    v-model="deleteSnackbarVisible"
    color="success"
    :timeout="3000"
  >
    {{ deleteSnackbarMessage }}
  </v-snackbar>
</template>

<script setup>
import { ref } from 'vue'
import { Polygon } from 'ol/geom'
import { getArea } from 'ol/sphere'
import { useMapStore } from '@/stores/map'

const API_BASE_URL = '/api/segmentation' // backend API

const mapStore = useMapStore() // Pinia store

const history = ref([])
const loading = ref(false)
const error = ref(null)
const viewingId = ref(null)
const expandedId = ref(null)
const deleteDialogOpen = ref(false)
const pendingDelete = ref(null)
const deletingId = ref(null)
const deleteError = ref(null)
const deleteSnackbarVisible = ref(false)
const deleteSnackbarMessage = ref('')

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

// fetches single prediction result by query_id
async function fetchResultById(queryId) {
  const response = await fetch(`${API_BASE_URL}/results/${queryId}`)

  if (!response.ok) {
    throw new Error('Failed to fetch prediction result')
  }

  return response.json()
}

// helper function to fetch the GeoJSON file from the result object
async function fetchGeoJSONResponse(result) {
  const resultUrl = result.prediction?.result_url  // geoJson file URL from the result object

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

// toggle the inline details panel for a specific past prediction
function toggleDetails(item) {
  expandedId.value = expandedId.value === item.query_id ? null : item.query_id
}

function computeBboxArea(bbox) {
  if (!bbox) return null

  const ring = [
    [bbox.min_lon, bbox.min_lat],
    [bbox.max_lon, bbox.min_lat],
    [bbox.max_lon, bbox.max_lat],
    [bbox.min_lon, bbox.max_lat],
    [bbox.min_lon, bbox.min_lat],
  ]

  const polygon = new Polygon([ring])
  return getArea(polygon, { projection: 'EPSG:4326' })
}

function formatArea(sqm) {
  if (sqm == null) return ''
  return sqm > 1_000_000
    ? `${(sqm / 1_000_000).toFixed(2)} km²`
    : `${Math.round(sqm)} m²`
}

function isZeroShot(item) {
  return Boolean(item.prediction_type?.toLowerCase().includes('zero_shot'))
}

// Older predictions didn't persist `keywords`; fall back to the summary
// text, which already embeds the keyword (e.g. "Found 113 house polygons/clusters").
function resolveKeyword(item) {
  if (item.keywords && item.keywords.length) return item.keywords.join(', ')
  if (!item.summary) return null

  const forMatch = item.summary.match(/\bfor\s+(.+)$/i)
  if (forMatch) return forMatch[1]

  const countMatch = item.summary.match(/^Found\s+\d+\s+(.+?)\s+polygons\/clusters/i)
  if (countMatch) return countMatch[1]

  return null
}

// open the export dialog for a specific past prediction
function exportPrediction(item) {
  if (mapStore.currentQueryId !== item.query_id) {
    mapStore.setCurrentExport(null)
  }
  mapStore.setCurrentPrediction(item.query_id)
  mapStore.openExportDialog()
}

// view a specific prediction on the map
async function viewPrediction(item) {
  if (viewingId.value) return

  viewingId.value = item.query_id

  try {
    const result = await fetchResultById(item.query_id)

    const geojsonResponse = await fetchGeoJSONResponse(
      result
    )

    const geojson = await geojsonResponse.json()

    mapStore.setViewedPrediction(geojson, item.query_id, result.prediction)
    mapStore.historyDrawerOpen = false
  } catch (err) {
    error.value = err.message
  } finally {
    viewingId.value = null
  }
}

function openDeleteDialog(item) {
  if (deletingId.value) return

  pendingDelete.value = item
  deleteError.value = null
  deleteDialogOpen.value = true
}

function closeDeleteDialog() {
  if (deletingId.value) return

  deleteDialogOpen.value = false
  pendingDelete.value = null
  deleteError.value = null
}

async function readErrorDetail(response) {
  try {
    const body = await response.json()

    return typeof body.detail === 'string'
      ? body.detail
      : null
  } catch {
    return null
  }
}

function applyDeletedPrediction(queryId) {
  history.value = history.value.filter(
    (item) => item.query_id !== queryId,
  )

  if (expandedId.value === queryId) {
    expandedId.value = null
  }

  mapStore.clearPredictionForQuery(queryId)
}

async function confirmDelete() {
  if (!pendingDelete.value || deletingId.value) {
    return
  }

  const queryId = pendingDelete.value.query_id

  deletingId.value = queryId
  deleteError.value = null

  try {
    let response

    try {
      response = await fetch(
        `${API_BASE_URL}/results/${queryId}`,
        {
          method: 'DELETE',
        },
      )
    } catch {
      throw new Error(
        'The server could not be reached. ' +
        'Please check your connection and try again.',
      )
    }

    const alreadyDeleted = response.status === 404

    if (!response.ok && !alreadyDeleted) {
      const detail = await readErrorDetail(response)

      if (response.status === 409) {
        throw new Error(
          detail ||
          'This prediction is still being processed.',
        )
      }

      throw new Error(
        detail ||
        'The prediction could not be deleted. ' +
        'Please try again.',
      )
    }

    applyDeletedPrediction(queryId)

    deleteDialogOpen.value = false
    pendingDelete.value = null

    deleteSnackbarMessage.value = alreadyDeleted
      ? 'Prediction was already deleted.'
      : 'Prediction deleted.'

    deleteSnackbarVisible.value = true
  } catch (err) {
    deleteError.value =
      err instanceof Error
        ? err.message
        : 'The prediction could not be deleted.'
  } finally {
    deletingId.value = null
  }
}

// Format task label
function formatLabel(item) {
  if (!item.prediction_type) return 'Prediction'
  return item.prediction_type
    .replace(/_/g, ' ') // replace underscores with spaces
    .replace(/\b\w/g, (char) => char.toUpperCase()) // capitalize first letter of each word
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleString()
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

.history-item :deep(.v-list-item-subtitle) {
  opacity: 1 !important;
}

.item-subtitle {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  opacity: 1;
}

.item-date {
  font-size: 0.75rem;
  opacity: 1;
}

.keyword-chip {
  pointer-events: none;
}

.history-item {
  cursor: pointer;
}

.details-panel {
  padding: 8px 16px 12px;
  background: rgba(0, 0, 0, 0.03);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 4px 0;
  font-size: 13px;
}

.detail-label {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.6);
  white-space: nowrap;
}

.detail-value {
  text-align: right;
  word-break: break-all;
}

.bbox-coords {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.delete-summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 16px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
  font-size: 13px;
}

.delete-query-id {
  color: rgba(0, 0, 0, 0.6);
  font-family: monospace;
  overflow-wrap: anywhere;
}

</style>
