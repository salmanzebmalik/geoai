<template>
  <div v-if="visible" class="overlay-wrapper">
    <v-card class="overlay-card" elevation="8" rounded="lg">
      <v-card-text>
        <div class="message">
          <v-icon icon="mdi-loading" class="spin mr-2" />
          Prediction is running…
        </div>

        <v-progress-linear
          v-model="progress"
          color="success"
          height="12"
          rounded
          class="progress-bar"
        />
        <div class="progress-label">{{ Math.round(progress) }}%</div>
      </v-card-text>

      <v-card-actions class="justify-end">
        <!-- TODO: really cancel prediction if clicked -->
        <v-btn variant="tonal" color="white" size="small">
          Cancel prediction
        </v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()

const visible = ref(false)
const progress = ref(0)
let timer = null

// Watch for changes in the `isPredicting` state from the map store to show/hide the overlay and update progress
watch(() => mapStore.isPredicting, (predicting) => {
  if (predicting) {
    progress.value = 0
    visible.value = true

    const totalMs = Math.max((mapStore.areaSqm ?? 0) / 1_000_000 * 30000, 500)
    const tickMs = 100
    const maxProgress = 95

    timer = setInterval(() => {
      progress.value = Math.min(progress.value + (tickMs / totalMs) * maxProgress, maxProgress)
    }, tickMs)
  } else {
    clearInterval(timer)
    timer = null
    progress.value = 100
    // Keep the overlay visible for a short moment to show 100% progress, then hide it
    setTimeout(() => {
      visible.value = false
      progress.value = 0
    }, 600)
  }
})
</script>

<style scoped>
.overlay-wrapper {
  position: absolute;
  left: 300px;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 10;
}

.overlay-card {
  width: 380px;
  pointer-events: all;
  background-color: rgba(27, 46, 27);
  color: white;
}

.message {
  display: flex;
  align-items: center;
  font-size: 15px;
  margin-bottom: 16px;
  color: white;
}

.spin {
  animation: spin 1.2s linear infinite;
  color: #4caf50;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-bar {
  margin-bottom: 4px;
}

.progress-label {
  font-size: 11px;
  text-align: right;
  color: rgba(255, 255, 255, 0.6);
}
</style>
