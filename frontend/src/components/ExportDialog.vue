<template>
  <v-dialog v-model="open" max-width="760" scrollable>
    <v-card>
      <v-card-title>Export annotations</v-card-title>
      <v-card-subtitle>
        Prediction {{ mapStore.currentQueryId }}
      </v-card-subtitle>

      <v-card-text>
        <v-row dense>
          <v-col cols="12">
            <v-select
              v-model="form.vector_formats"
              :items="vectorFormats"
              item-title="title"
              item-value="value"
              label="Vector formats"
              multiple
              chips
            />
          </v-col>
          <v-col cols="12" sm="6">
            <v-combobox
              v-model="form.output_crs"
              :items="['EPSG:4326', 'EPSG:3857', 'EPSG:25832']"
              label="Output CRS"
            />
          </v-col>
          <v-col cols="12" sm="3">
            <v-text-field
              v-model="form.overlay_color"
              label="Overlay color"
              type="color"
            />
          </v-col>
          <v-col cols="12" sm="3">
            <v-slider
              v-model="form.overlay_opacity"
              label="Opacity"
              :min="0"
              :max="1"
              :step="0.05"
              thumb-label
            />
          </v-col>
        </v-row>

        <div class="option-grid">
          <v-checkbox v-model="form.include_annotated_tiff" label="Annotated GeoTIFF" hide-details />
          <v-checkbox v-model="form.include_mask_tiff" label="Mask GeoTIFF" hide-details />
          <v-checkbox v-model="form.include_metadata" label="Metadata JSON" hide-details />
          <v-checkbox v-model="form.include_zip" label="ZIP bundle" hide-details />
        </div>

        <v-expansion-panels variant="accordion" class="mt-4">
          <v-expansion-panel title="Feature filters">
            <v-expansion-panel-text>
              <v-row dense>
                <v-col cols="12" sm="4">
                  <v-text-field v-model.number="form.filters.min_area_m2" type="number" min="0" label="Min. area (m²)" clearable />
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field v-model.number="form.filters.max_area_m2" type="number" min="0" label="Max. area (m²)" clearable />
                </v-col>
                <v-col cols="12" sm="4">
                  <v-text-field v-model.number="form.filters.min_confidence" type="number" min="0" max="1" step="0.05" label="Min. confidence" clearable />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select
                    v-model="form.filters.geometry_types"
                    :items="['Polygon', 'MultiPolygon']"
                    label="Geometry types"
                    multiple
                    clearable
                  />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-text-field
                    v-model="labels"
                    label="Labels (comma-separated)"
                    placeholder="building, car"
                    clearable
                  />
                </v-col>
              </v-row>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>

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
                  icon="mdi-folder-zip"
                  size="small"
                  variant="text"
                  @click="download(item.artifacts.find((artifact) => artifact.name === 'zip'))"
                />
              </template>
            </v-list-item>
          </v-list>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">Close</v-btn>
        <v-btn
          color="success"
          prepend-icon="mdi-export"
          :loading="mapStore.isExporting"
          :disabled="!hasOutput"
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
const labels = ref('')
const history = ref([])

const vectorFormats = [
  { title: 'GeoJSON', value: 'geojson' },
  { title: 'GeoPackage', value: 'gpkg' },
  { title: 'FlatGeobuf', value: 'flatgeobuf' },
  { title: 'Shapefile (ZIP)', value: 'shapefile' },
]

const form = reactive({
  vector_formats: ['geojson'],
  output_crs: 'EPSG:4326',
  overlay_color: '#ff0000',
  overlay_opacity: 0.45,
  include_annotated_tiff: true,
  include_mask_tiff: false,
  include_metadata: true,
  include_zip: true,
  filters: {
    min_area_m2: null,
    max_area_m2: null,
    min_confidence: null,
    geometry_types: [],
  },
})

const hasOutput = computed(() => (
  form.vector_formats.length > 0
  || form.include_annotated_tiff
  || form.include_mask_tiff
  || form.include_metadata
  || form.include_zip
))

watch(() => mapStore.exportDialogTrigger, () => {
  open.value = true
  error.value = null
  loadHistory()
})

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
      include_geojson: form.vector_formats.includes('geojson'),
      filters: {
        ...form.filters,
        labels: labels.value
          .split(',')
          .map((label) => label.trim())
          .filter(Boolean),
      },
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
.option-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
