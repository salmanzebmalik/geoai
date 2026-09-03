<template>
  <div v-if="visible" class="overlay-wrapper">
    <v-card class="overlay-card" color="#1b2e1b" elevation="8" rounded="lg">
      <v-card-text>
        <div class="message">
          <v-progress-circular indeterminate size="20" width="2" color="success" class="mr-2" />
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
    </v-card>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore() // Pinia store

const visible = ref(false)
const progress = ref(0)
let timer = null

// simulated progress bar based on area size
watch(() => mapStore.isPredicting, (predicting) => {
  if (predicting) {
    progress.value = 0
    visible.value = true

    // estimation for total time based on area size (min 500ms)
    const totalMs = Math.max((mapStore.areaSqm ?? 0) / 1_000_000 * 200000, 500) // 1500 seconds per square kilometer, minimum 0.5 seconds
    const tickMs = 100 // update progress every 100ms
    const maxProgress = 95 // don't reach 100% until prediction is done

    // timer to update progress bar
    timer = setInterval(() => {
      progress.value = Math.min(progress.value + (tickMs / totalMs) * maxProgress, maxProgress)
    }, tickMs)
  
  } else {
    clearInterval(timer)
    timer = null

    // Keep the overlay visible for a short moment to show 100% progress, then hide it
    progress.value = 100
  
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
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 10;
}

.overlay-card {
  width: 380px;
  pointer-events: all;
}

.message {
  display: flex;
  align-items: center;
  font-size: 15px;
  margin-bottom: 16px;
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
