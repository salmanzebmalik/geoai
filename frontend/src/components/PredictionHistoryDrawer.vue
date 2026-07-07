<template>
  <v-btn
    icon="mdi-history"
    class="history-toggle"
    :class="{ 'history-toggle--shifted': drawerOpen }"
    color="success"
    @click="toggleDrawer"
  />

  <v-navigation-drawer
    v-model="drawerOpen"
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
      <v-list-item v-for="item in history" :key="item.query_id">
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
            @click="downloadPrediction(item)"
          />
        </template>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { ref } from 'vue'

const API_BASE_URL = 'http://localhost:8002/api/segmentation'

const drawerOpen = ref(false)
const history = ref([])
const loading = ref(false)
const error = ref(null)
const downloadingId = ref(null)

function toggleDrawer() {
  drawerOpen.value = !drawerOpen.value

  if (drawerOpen.value && history.value.length === 0) {
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

async function downloadPrediction(item) {
  downloadingId.value = item.query_id

  try {
    const response = await fetch(`${API_BASE_URL}/results/${item.query_id}`)

    if (!response.ok) {
      throw new Error('Failed to fetch prediction result')
    }

    const result = await response.json()
    const geojson = result.prediction?.geojson

    if (!geojson) return

    const blob = new Blob([JSON.stringify(geojson, null, 2)], {
      type: 'application/geo+json',
    })
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
</style>
