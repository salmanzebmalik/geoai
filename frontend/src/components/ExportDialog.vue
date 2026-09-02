<template>
  <v-dialog v-model="open" max-width="680" scrollable>
    <v-card class="export-dialog-card" rounded="lg" elevation="16">
      <v-card-title class="export-title">
        <v-icon icon="mdi-tray-arrow-down" size="small" />
        Export annotations
      </v-card-title>
      <v-card-subtitle class="export-subtitle">
        Prediction {{ mapStore.currentQueryId }}
      </v-card-subtitle>

      <v-card-text class="export-content">
        <div class="export-controls">
          <v-text-field
            v-model="form.overlay_color"
            label="Overlay color"
            type="color"
            variant="outlined"
            density="comfortable"
            hide-details
          />

          <div class="opacity-control">
            <div class="control-label">Opacity</div>
            <v-slider
              v-model="form.overlay_opacity"
              :min="0"
              :max="1"
              :step="0.05"
              thumb-label
              color="success"
              track-color="grey-darken-1"
              hide-details
            />
          </div>
        </div>

        <v-alert v-if="error" type="error" variant="tonal" class="mt-4">
          {{ error }}
        </v-alert>

        <div v-if="mapStore.currentExport" class="mt-5">
          <div class="section-title">
            Exported {{ mapStore.currentExport.exported_feature_count }} of
            {{ mapStore.currentExport.source_feature_count }} features
          </div>
          <div class="artifact-list">
            <v-btn
              v-for="artifact in mapStore.currentExport.artifacts"
              :key="artifact.name"
              size="small"
              variant="tonal"
              prepend-icon="mdi-download"
              @click="download(artifact)"
            >{{ artifact.name }}</v-btn>
          </div>
        </div>

        <div v-if="history.length" class="mt-5">
          <div class="section-title">Recent exports</div>
          <v-list density="compact">
            <v-list-item
              v-for="item in history.slice(0, 5)"
              :key="item.export_id"
              :title="`${item.exported_feature_count} features · ${item.output_crs}`"
              :subtitle="new Date(item.created_at).toLocaleString()"
            >
              <template #append>
                <v-btn
                  v-if="item.artifacts.find((artifact) => artifact.name === 'zip')"
                  icon="mdi-download"
                  size="small"
                  variant="text"
                  @click="download(item.artifacts.find((artifact) => artifact.name === 'zip'))"
                />
              </template>
            </v-list-item>
          </v-list>
        </div>
      </v-card-text>

      <v-card-actions class="export-actions">
        <v-spacer />
        <v-btn variant="text" @click="open = false">Close</v-btn>
        <v-btn
          color="success"
          prepend-icon="mdi-export"
          :loading="mapStore.isExporting"
          @click="createExport"
        >Create export</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
const open = ref(false)
const error = ref(null)
const history = ref([])

const form = reactive({
  overlay_color: '#ff0000',
  overlay_opacity: 0.45,
})

watch(() => mapStore.exportDialogTrigger, () => {
  open.value = true
  error.value = null
  loadHistory()
})

watch(
  () => mapStore.currentQueryId,
  (queryId) => {
    if (queryId || !open.value) return

    open.value = false
    history.value = []
    error.value = null
  },
)

async function loadHistory() {
  if (!mapStore.currentQueryId) return
  try {
    const response = await fetch(
      `/api/segmentation/exports?query_id=${mapStore.currentQueryId}`
    )
    if (response.ok) history.value = await response.json()
  } catch {
    // History is supplementary; export creation remains available.
  }
}

async function createExport() {
  mapStore.isExporting = true
  error.value = null
  try {
    const options = {
      ...form,
      vector_formats: ['geojson'],
      output_crs: 'EPSG:4326',
      include_geojson: true,
      include_annotated_tiff: true,
      include_mask_tiff: true,
      include_metadata: true,
      include_zip: true,
    }
    const response = await fetch('/api/segmentation/exports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query_id: mapStore.currentQueryId, options }),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || 'Export failed')
    mapStore.setCurrentExport(result)
    await loadHistory()
  } catch (err) {
    error.value = err.message
  } finally {
    mapStore.isExporting = false
  }
}

function download(artifact) {
  window.open(artifact.download_url, '_blank', 'noopener')
}
</script>

<style scoped>
.export-dialog-card {
  padding: 8px;
}

.export-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px 8px;
  font-size: 1.25rem;
  font-weight: 600;
}

.export-subtitle {
  padding: 0 20px 14px;
}

.export-content {
  padding: 16px 20px;
}

.export-controls {
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 16px;
  background: rgba(72, 72, 72, 0.035);
  border: 1px solid rgba(69, 67, 67, 0.08);
  border-radius: 10px;
}

.opacity-control {
  padding: 0 4px 4px;
}

.control-label {
  margin-bottom: 8px;
  font-size: 0.82rem;
}

.export-actions {
  padding: 10px 16px 14px;
}

.section-title {
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 8px;
}

.artifact-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
