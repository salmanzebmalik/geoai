<template>
  <v-navigation-drawer permanent width="300" color="#1b2e1b">
    <!--  Map picker -->
      <div class="map-picker">
        <div class="picker-title">
          <v-icon size="18" class="mr-2">mdi-layers</v-icon>
          <p class="picker-label">MAP</p>
        </div>
        <v-select
          v-model="mapStore.mapType"
          :items="mapTypeOptions"
          variant="outlined"
          density="comfortable"
          hide-details
          class="map-type-select"
        >
          <template #item="{ item, props: itemProps }">
            <v-list-item v-bind="itemProps" title="" class="map-select-item">
              <template #prepend>
                <img :src="item.thumbnail" alt="" class="map-thumb" />
              </template>
              <v-list-item-title class="map-item-title">{{ item.title }}</v-list-item-title>
              <v-list-item-subtitle class="map-item-subtitle">{{ item.description }}</v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-select>

        <div class="sentinel-controls" v-if="mapStore.mapType === 'sentinel'">
          <div class="sentinel-label">
            <v-icon size="16" class="mr-2">mdi-cloud</v-icon>
            <p>Max. cloud coverage</p>
          </div>
          <div class="cloud-slider-row">
            <v-slider
              v-model="mapStore.sentinelMaxCloudCover"
              :min="0"
              :max="100"
              :step="1"
              hide-details
              color="#a5d6a7"
              track-color="rgba(255, 255, 255, 0.25)"
              thumb-size="15"
              class="cloud-slider"
              @end="mapStore.triggerSentinelRefresh()"
            ></v-slider>
            <span class="cloud-value">{{ mapStore.sentinelMaxCloudCover }}%</span>
          </div>

          <div class="sentinel-label">
            <v-icon size="16" class="mr-2">mdi-calendar-range</v-icon>
            <span>Date range</span>
          </div>
          <v-date-picker
            v-model="sentinelDateRange"
            multiple="range"
            show-adjacent-months
            hide-header
            first-day-of-week="1"
            theme="dark"
            color="#8bc34a"
            bg-color="transparent"
            elevation="0"
            width="100%"
            :min="sentinelMinDate"
            :max="sentinelMaxDate"
            class="sentinel-date-picker"
          >
            <template #controls="{ monthText, yearText, openMonths, openYears }">
              <v-sheet
                class="w-100 d-flex align-center rounded-lg pa-1 ga-1"
                color="rgba(255, 255, 255, 0.08)"
              >
                <v-btn :text="monthText" append-icon="$dropdown" size="small" variant="tonal" class="px-2" @click="openMonths"></v-btn>
                <v-btn :text="yearText" append-icon="$dropdown" size="small" variant="tonal" class="px-2" @click="openYears"></v-btn>
              </v-sheet>
            </template>
          </v-date-picker>
        </div>
      </div>

      <v-divider/>
    
      <v-list class="procedure" lines="one">
        <!-- Area selection -->
          <v-list-item
            prepend-icon="mdi-numeric-1-circle"
            title="Area"
          ></v-list-item>
          
          <div class="area-buttons">
            <v-btn
              @click="mapStore.triggerDrawing()"
              class="select-button"
              prepend-icon="mdi-select"
            >Select Area</v-btn>

            <v-btn
              @click="mapStore.coordinateInputOpen = true"
              class="input-coords-button"
              aria-label="Enter coordinates manually"
              variant="tonal"
            >
              <v-icon icon="mdi-pencil" />
            </v-btn>
          </div>

          <div class="bbox-info" v-if="mapStore.bbox">
            <div class="bbox-coords">
              <span>N {{ mapStore.bbox.max_lat.toFixed(5) }}</span>
              <span>S {{ mapStore.bbox.min_lat.toFixed(5) }}</span>
              <span>E {{ mapStore.bbox.max_lon.toFixed(5) }}</span>
              <span>W {{ mapStore.bbox.min_lon.toFixed(5) }}</span>
            </div>
            <div class="bbox-area">
              <span class="area">{{ formatArea(mapStore.areaSqm) }}</span>
              <span class="area-fields">~ {{ formatSoccerFields(mapStore.areaSqm) }} soccer fields</span>
            </div>
          </div>

          <div
            v-if="mapStore.bbox && supportsPredictionMap"
            class="raster-estimate"
            :class="{
              'raster-estimate--blocked':
                mapStore.rasterEstimate &&
                !mapStore.rasterEstimate.allowed,
              'raster-estimate--error':
                mapStore.rasterEstimateError,
            }"
          >
            <div class="raster-estimate-title">
              <v-icon size="15">mdi-image-size-select-large</v-icon>
              <span>Estimated raster</span>
            </div>

            <div
              v-if="mapStore.isEstimatingRaster"
              class="raster-estimate-loading"
            >
              <v-progress-circular
                indeterminate
                size="14"
                width="2"
              />
              <span>Calculating workload…</span>
            </div>

            <template v-else-if="mapStore.rasterEstimate">
              <span class="raster-estimate-size">
                {{
                  formatPixelCount(
                    mapStore.rasterEstimate.width_pixels,
                  )
                }}
                ×
                {{
                  formatPixelCount(
                    mapStore.rasterEstimate.height_pixels,
                  )
                }}
                pixels
                ({{ formatMegapixels(mapStore.rasterEstimate.megapixels) }} MP)
              </span>

              <span
                class="raster-estimate-status"
                :class="{
                  'raster-estimate-status--blocked':
                    !mapStore.rasterEstimate.allowed,
                }"
              >
                {{
                  mapStore.rasterEstimate.allowed
                    ? 'Within current processing limit'
                    : 'Area exceeds current processing limit'
                }}
              </span>

              <span class="raster-estimate-limit">
                Limit:
                {{
                  formatMegapixels(
                    mapStore.rasterEstimate.max_total_pixels / 1_000_000,
                  )
                }}
                MP total /
                {{
                  formatPixelCount(
                    mapStore.rasterEstimate.max_side_pixels,
                  )
                }}
                px per side
              </span>
            </template>

            <span
              v-else-if="mapStore.rasterEstimateError"
              class="raster-estimate-status raster-estimate-status--blocked"
            >
              {{ mapStore.rasterEstimateError }}
            </span>
          </div>
          <!-- Task selection  -->
          <v-list-item
            prepend-icon="mdi-numeric-2-circle"
            title="Task"
          ></v-list-item>
          
          <v-select
            :items="availableTasks"
            :disabled="!availableTasks.length"
            :placeholder="availableTasks.length ? 'Select Task' : 'No tasks available'"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
            v-model="mapStore.selectedTask"
            @update:model-value="onTaskChange"
          ></v-select>

          <template v-if="mapStore.selectedTask === 'Zero-Shot'">
          <v-list-item prepend-icon="mdi-plus" title="Keywords" />
          <v-text-field
            v-model="mapStore.keyword"
            placeholder="buildings, pools, cars"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
            prepend-inner-icon="mdi-magnify"
            @keyup.enter="mapStore.triggerRun()"
          />
        </template>

        <!-- Model selection -->
          <v-list-item
            prepend-icon="mdi-numeric-3-circle"
            title="Model"
          ></v-list-item>
          
          <v-select
            :items="modelOptions"
            :disabled="!modelOptions.length"
            :placeholder= "modelOptions.length ? 'Select Model' : 'No models available'"
            v-model="mapStore.modelType"
            variant="solo"
            density="compact"
            class="ml-task-dropdown"
            hide-details
          ></v-select>

          <!-- Start prediction button-->
          <v-list-item
            prepend-icon="mdi-numeric-4-circle"
            title="Start Prediction"
          ></v-list-item>
          
          <v-btn
            @click="mapStore.triggerRun()"
            prepend-icon="mdi-rocket-launch"
            class="run-btn"
            color="success"
            :disabled="
              mapStore.isPredicting ||
              mapStore.mapType === 'osm' ||
              !mapStore.bbox ||
              !mapStore.selectedTask ||
              (mapStore.selectedTask === 'Zero-Shot' && !mapStore.keyword.trim())
            "
          >Run</v-btn>

          <v-list-item
            prepend-icon="mdi-numeric-5-circle"
            title="Export"
          ></v-list-item>
          <v-btn
            @click="mapStore.openExportDialog()"
            prepend-icon="mdi-tray-arrow-down"
            class="run-btn"
            color="success"
            variant="tonal"
            :disabled="!mapStore.currentQueryId"
          >Export options</v-btn>
      </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useMapStore } from '@/stores/map'
import osmThumb from '@/assets/map-osm.jpg'
import germanyThumb from '@/assets/map-germany.jpg'
import orthophotoThumb from '@/assets/map-orthophoto.jpg'
import sentinelThumb from '@/assets/map-sentinel.jpg'

const mapStore = useMapStore()
const supportsPredictionMap = computed(() =>
  ['orthophoto', 'germany'].includes(mapStore.mapType)
)

const runDisabled = computed(() => {
  const zeroShotKeywordMissing =
    mapStore.selectedTask === 'Zero-Shot'
    && !mapStore.keyword.trim()

  return (
    !supportsPredictionMap.value
    || !mapStore.bbox
    || !mapStore.selectedTask
    || zeroShotKeywordMissing
    || mapStore.isEstimatingRaster
    || Boolean(mapStore.rasterEstimateError)
    || !mapStore.rasterEstimate
    || !mapStore.rasterEstimate.allowed
  )
})

function formatPixelCount(value) {
  return Number(value).toLocaleString()
}

function formatMegapixels(value) {
  return Number(value).toFixed(2)
}

// Some element in this densely interactive sidebar (menus/overlays call
// stopPropagation() on their own click handling) can swallow a mouseup before
// it bubbles up to window, which is where v-slider listens to end a drag -
// leaving the cloud-cover slider's thumb stuck following the cursor. A
// capture-phase listener always fires before that interference, so redispatch
// the release straight at window to make sure the slider actually sees it.
function releaseStuckDrag(e) {
  if (!e.isTrusted) return // ignore the synthetic event this handler itself dispatches
  window.dispatchEvent(new MouseEvent('mouseup', {
    bubbles: false,
    cancelable: true,
    clientX: e.clientX,
    clientY: e.clientY,
    button: e.button,
  }))
}

onMounted(() => window.addEventListener('mouseup', releaseStuckDrag, { capture: true }))
onUnmounted(() => window.removeEventListener('mouseup', releaseStuckDrag, { capture: true }))

const mapTypeOptions = [
  {
    title: 'NRW',
    value: 'orthophoto',
    description: 'High-resolution aerial imagery (10cm/px; 2021/2022)',
    thumbnail: orthophotoThumb,
  },
  {
    title: 'Germany',
    value: 'germany',
    description: 'Coarse aerial imagery (3-5m/px; 2020)',
    thumbnail: germanyThumb,
  },
  {
    title: 'Sentinel',
    value: 'sentinel',
    description: 'Satellite imagery (10m/px; 2018-2024 available)',
    thumbnail: sentinelThumb,
  },
  {
    title: 'OSM',
    value: 'osm',
    description: 'Open street map (no prediction)',
    thumbnail: osmThumb,
  },
]

const TASK_OPTIONS_BY_MAP_TYPE = {
  orthophoto: [
    { title: 'Tree Detection', value: 'Tree Detection' },
    { title: 'Segment Anything', value: 'Zero-Shot' },
  ],
  germany: [
    { title: 'Tree Detection', value: 'Tree Detection' },
  ],
  osm: [],
  sentinel: [
    { title: 'Tree Detection', value: 'Tree Detection' },
  ],
}

const availableTasks = computed(() => TASK_OPTIONS_BY_MAP_TYPE[mapStore.mapType] ?? [])

// only the models that match the current dataset's resolution are displayed 
const TREE_MODELS_BY_MAP_TYPE = {
  orthophoto: [
    { title: 'TCD-Segformer', value: 'tree' },
    { title: 'DeepForest Boxes', value: 'tree_deepforest' },
  ],
  germany: [
    { title: 'Satlas', value: 'tree_satlas' },
    { title: 'UNet', value: 'tree_unet' },
  ],
  osm: [],
  // Satlas only, matching MODELS_BY_SOURCE["sentinel"] in the backend -- the
  // API rejects anything else for this source. UNet is omitted because its
  // checkpoint is missing, Segformer because it is trained at ~10 cm and
  // Sentinel is 10 m.
  sentinel: [
    { title: 'Satlas', value: 'tree_satlas' },
  ],
}

const modelOptions = computed(() =>
  mapStore.selectedTask === 'Zero-Shot'
    ? [{ title: 'LangSAM', value: 'zeroshot' }]
    : TREE_MODELS_BY_MAP_TYPE[mapStore.mapType] ?? []
)

//Sentinel date range picker
// v-date-picker (multiple="range") works with Date objects
const sentinelMinDate = new Date(2018, 0, 1)
const sentinelMaxDate = new Date(2024, 11, 31)

function fromISODate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function toISODate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const sentinelDateRange = ref([
  fromISODate(mapStore.sentinelDateFrom),
  fromISODate(mapStore.sentinelDateTo),
])

// Only commit + trigger a refresh once a full [start, end] range is picked
watch(sentinelDateRange, (range) => {
  if (range.length !== 2) return
  mapStore.sentinelDateFrom = toISODate(range[0])
  mapStore.sentinelDateTo = toISODate(range[1])
  mapStore.triggerSentinelRefresh()
})

watch(() => mapStore.mapType, () => {
  if (!availableTasks.value.some((t) => t.value === mapStore.selectedTask)) {
    mapStore.selectedTask = availableTasks.value[0]?.value ?? null
  }
  onTaskChange()
})

function formatArea(sqm) {
  if (sqm == null) return ''
  return sqm > 1_000_000
    ? `${(sqm / 1_000_000).toFixed(2)} km²`
    : `${Math.round(sqm)} m²`
}

const SOCCER_FIELD_SQM = 7140

function formatSoccerFields(sqm) {
  if (sqm == null) return ''
  return (sqm / SOCCER_FIELD_SQM).toFixed(0)
}

// Update model type based on selected task
function onTaskChange() {
  if (mapStore.selectedTask === 'Zero-Shot') {
    mapStore.modelType = 'zeroshot'
  } else if (mapStore.selectedTask) {
    mapStore.modelType = modelOptions.value[0]?.value ?? null
    mapStore.keyword = ''   // clear keyword for non zero shot
  } else {
    mapStore.modelType = null
    mapStore.keyword = ''
  }
}

</script>

<style scoped>
.map-picker {
  padding: 16px 16px 12px;

  .v-btn {
    flex: 1;
  }
}

.picker-title {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.picker-label {
  font-size: 11px;
  margin: 0;
}

.map-type-select {
  width: 100%;
}

.map-type-select :deep(.v-field) {
  color: white;
}

.map-type-select :deep(.v-field__outline) {
  --v-field-border-opacity: 0.3;
}

.sentinel-controls {
  margin-top: 14px;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sentinel-label {
  display: flex;
  align-items: center;
  font-size: 11px;
  text-transform: uppercase;
  margin-top: 8px;
}

.sentinel-label:first-child {
  margin-top: 0;
}

.sentinel-label p {
  margin: 0;
}

.cloud-slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cloud-slider {
  flex: 1;
}

.cloud-value {
  font-size: 13px;
  font-weight: 600;
  color: #a5d6a7;
  min-width: 32px;
  text-align: right;
}

.sentinel-date-picker {
  align-self: center;
  overflow: hidden;
}

.sentinel-date-picker :deep(.v-picker__body) {
  background: transparent;
}

.sentinel-date-picker :deep(.v-date-picker-month__day-btn) {
  --v-btn-size: 12px;
  --v-btn-height: 26px;
  /* Override circle size to force that the button stays a circle instead of the oval due to other resizing. */
  width: 26px !important;
  height: 26px !important;
}

/* Override between-dates days circle color  */
.sentinel-date-picker :deep(.v-date-picker-month__day--selected .v-btn) {
  background-color: #a5d6a78c;
}

/* Shrink the day-cell grid itself */
.sentinel-date-picker :deep(.v-date-picker-month) {
  padding: 0 4px 8px;
}

.sentinel-date-picker :deep(.v-date-picker-month__days) {
  column-gap: 2px;
}

.sentinel-date-picker :deep(.v-date-picker-month__day) {
  width: 28px;
  height: 28px;
}

/* Override the year dropdown to 2 and not 3 columns */
.sentinel-date-picker :deep(.v-date-picker-years__content) {
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 12px;
  padding-inline: 8px;
}

/* Override year selection hight because we only ever need 4 rows. */
.sentinel-date-picker :deep(.v-date-picker-years) {
  height: auto;
  max-height: 220px;
  overflow-y: auto;
}

.map-select-item {
  padding-inline-start: 8px;
}

.map-thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.map-item-title {
  font-size: 13px;
  font-weight: 500;
  margin-left: 8px;
}

.map-item-subtitle {
  font-size: 11px;
  opacity: 0.7;
  white-space: normal;
  margin-left: 8px;
}

.area-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 90%;
  margin: 0 16px;
}

.select-button {
  flex: 1;
  min-width: 0;
}

.input-coords-button {
  flex-shrink: 0;
  min-width: 0;
  padding: 0 14px;
}

.ml-task-dropdown {
  width: 90%;
  margin: 0 16px;
}

.run-btn {
  width: 90%;
  margin: 0 16px;
}

.run-btn.v-btn--disabled {
  opacity: 40%;
  background-color: grey;
}

.bottom-actions {
  display: flex;
  justify-content: flex-start;
  padding: 8px 12px;
}

.bbox-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 90%;
  margin: 8px 16px;
  padding: 10px 12px;
  background-color: rgba(139, 195, 74, 0.1);
  border: 1px solid rgba(139, 195, 74, 0.2);
  border-radius: 8px;
  font-size: 12px;
}

.bbox-coords {
  display: grid;
  grid-template-columns: auto auto;
  column-gap: 8px;
  row-gap: 2px;
  color: rgba(255, 255, 255, 0.85);
}

.bbox-area {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.area {
  color: #a5d6a7;
  white-space: nowrap;
}

.area-fields {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  white-space: nowrap;
}


.raster-estimate {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 90%;
  margin: 8px 16px;
  padding: 9px 11px;
  border: 1px solid rgba(139, 195, 74, 0.28);
  border-radius: 8px;
  background: rgba(139, 195, 74, 0.08);
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.raster-estimate--blocked,
.raster-estimate--error {
  border-color: rgba(239, 83, 80, 0.55);
  background: rgba(239, 83, 80, 0.1);
}

.raster-estimate-title,
.raster-estimate-loading {
  display: flex;
  align-items: center;
  gap: 6px;
}

.raster-estimate-title {
  color: rgba(255, 255, 255, 0.65);
  font-weight: 600;
}

.raster-estimate-size {
  color: white;
}

.raster-estimate-status {
  color: #a5d6a7;
}

.raster-estimate-status--blocked {
  color: #ef9a9a;
}

.raster-estimate-limit {
  color: rgba(255, 255, 255, 0.5);
}

</style>