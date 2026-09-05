<template>
  <v-dialog v-model="open" max-width="680" scrollable>
    <v-card class="export-dialog-card" rounded="lg" elevation="16">
      <v-card-title class="export-title">
        <v-icon icon="mdi-tray-arrow-down" size="small" />
        Export Prediction
      </v-card-title>
      <v-card-subtitle class="export-subtitle">
        Prediction {{ mapStore.currentQueryId }}
      </v-card-subtitle>

      <v-card-text class="export-content">
        <section v-if="hasClasses" class="export-section">
          <div class="section-head">
            <span class="section-title">Classes</span>
            <span class="section-count">
              {{ selectedClasses.length }} of {{ allClassNames.length }}
            </span>
          </div>

          <v-chip-group
            v-model="selectedClasses"
            multiple
            filter
            class="class-chips"
          >
            <v-chip
              v-for="entry in mapStore.predictionClasses"
              :key="entry.name"
              :value="entry.name"
              variant="outlined"
              size="small"
              :ripple="false"
            >
              <span
                class="class-color-swatch"
                :style="{ backgroundColor: entry.color }"
              />
              {{ entry.name }}
            </v-chip>
          </v-chip-group>

          <v-alert
            v-if="!selectedClasses.length"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-2"
          >
            Select at least one class to export.
          </v-alert>
        </section>

        <section class="export-section">
          <div class="section-head">
            <span class="section-title">Overlay</span>
          </div>

          <v-text-field
            v-if="singleClassPrediction"
            v-model="form.overlay_color"
            label="Overlay color"
            type="color"
            variant="outlined"
            density="comfortable"
            hide-details
            class="overlay-color"
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
        </section>

        <v-alert v-if="error" type="error" variant="tonal" class="mt-4">
          {{ error }}
        </v-alert>

        <section v-if="mapStore.currentExport" class="export-section">
          <div class="section-head">
            <span class="section-title">Result</span>
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
        </section>

        <section v-if="history.length" class="export-section">
          <div class="section-head">
            <span class="section-title">Recent exports</span>
          </div>
          <v-list density="compact" class="history-list">
            <v-list-item
              v-for="item in history.slice(0, 5)"
              :key="item.export_id"
              :title="modelLabel(item)"
              :subtitle="formatTimestamp(item.created_at)"
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
        </section>
      </v-card-text>

      <v-card-actions class="export-actions">
        <v-spacer />
        <v-btn variant="text" @click="open = false">Close</v-btn>
        <v-btn
          color="success"
          prepend-icon="mdi-export"
          :loading="mapStore.isExporting"
          :disabled="!canExport"
          @click="createExport"
        >Create export</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
const open = ref(false)
const error = ref(null)
const history = ref([])

const form = reactive({
  overlay_color: '#ff0000',
  overlay_opacity: 0.45,
})

const exportsDisplayedPrediction = computed(
  () => Boolean(mapStore.currentQueryId)
    && mapStore.viewedQueryId === mapStore.currentQueryId,
)

const hasClasses = computed(
  () => exportsDisplayedPrediction.value && mapStore.predictionClasses.length > 0,
)

const allClassNames = computed(() =>
  mapStore.predictionClasses.map((entry) => entry.name),
)

const selectedClasses = ref([])

function isSelected(name) {
  return selectedClasses.value.includes(name)
}

function resetClassSelection() {
  const visible = mapStore.predictionClasses
    .map((entry) => entry.name)
    .filter((name) => !mapStore.hiddenPredictionClasses.includes(name))

  selectedClasses.value = visible.length ? visible : [...allClassNames.value]
}

watch(() => mapStore.predictionClasses, resetClassSelection)

const exportedClasses = computed(() =>
  mapStore.predictionClasses.filter((entry) => isSelected(entry.name)),
)

const usesClassColors = computed(() => exportedClasses.value.length > 1)

const singleClassPrediction = computed(() => allClassNames.value.length <= 1)

const MODEL_LABELS = {
  zeroshot: 'Zero-Shot',
  tree: 'TCD-Segformer',
  tree_deepforest: 'DeepForest',
  tree_satlas: 'Satlas',
  tree_unet: 'UNet',
  tree_satlas_sentinel: 'Satlas (Sentinel)',
  tree_unet_sentinel: 'UNet (Sentinel)',
  yolo: 'YOLO11',
}

function modelLabel(item) {
  return MODEL_LABELS[item?.model_type] ?? item?.model_type ?? 'Export'
}

function formatTimestamp(value) {
  return new Date(value).toLocaleString()
}


const classFilter = computed(() =>
  hasClasses.value
    && selectedClasses.value.length
    && selectedClasses.value.length < allClassNames.value.length
      ? selectedClasses.value
      : null,
)

const canExport = computed(
  () => Boolean(mapStore.currentQueryId)
    && (!hasClasses.value || selectedClasses.value.length > 0),
)

watch(() => mapStore.exportDialogTrigger, () => {
  open.value = true
  error.value = null
  resetClassSelection()
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

    if (classFilter.value) {
      options.filters = { labels: classFilter.value }
    }

    if (usesClassColors.value) {
      options.label_colors = Object.fromEntries(
        exportedClasses.value.map((entry) => [entry.name, entry.color]),
      )
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

.class-color-swatch {
  width: 12px;
  height: 12px;
  margin-right: 7px;
  flex: none;
  border-radius: 3px;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.15);
}

.export-section {
  padding: 14px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.export-section:first-child {
  padding-top: 6px;
}

.export-section:last-child {
  border-bottom: 0;
  padding-bottom: 4px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.section-count {
  font-size: 0.78rem;
  color: rgba(0, 0, 0, 0.6);
}

.section-hint {
  font-size: 0.78rem;
  color: rgba(0, 0, 0, 0.6);
  margin-bottom: 10px;
}

.class-chips {
  margin-left: -2px;
}

.overlay-color {
  max-width: 220px;
}

.class-chip--off {
  opacity: 0.5;
}

.class-chip--off .class-color-swatch {
  background-color: transparent !important;
}

.class-actions {
  margin-left: -8px;
}

.history-list {
  background: transparent;
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
  padding: 0 20px 2px;
}

.export-content {
  padding: 0 20px 16px;
}

.opacity-control {
  margin-top: 14px;
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
}

.artifact-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
