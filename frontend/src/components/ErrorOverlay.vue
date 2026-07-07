<template>
  <div v-if="mapStore.errorMessage" class="overlay-wrapper">
    <v-card class="overlay-card" color="#2e1b1b" elevation="8" rounded="lg">
      <v-card-text class="card-body">
        <div class="error-title">
          <v-icon color="error" size="20" class="mr-2">mdi-alert-circle</v-icon>
          Error
        </div>
        <div class="error-message">{{ mapStore.errorMessage }}</div>
      </v-card-text>

      <v-card-actions class="card-actions">
        <v-btn
          variant="tonal"
          color="white"
          block
          @click="mapStore.clearError()"
        >
          Dismiss
        </v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script setup>
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
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
  width: 480px;
  pointer-events: all;
}

.card-body {
  padding: 50px 28px 20px;
  text-align: center;
}

.error-title {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  font-weight: 700;
  color: #ef9a9a;
  margin-bottom: 12px;
}

.error-message {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.75);
}

.card-actions {
  padding: 0 28px 50px;
}
</style>
