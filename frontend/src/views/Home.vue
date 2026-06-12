<template>
  <div class="home">
    <MapView />
    <NavigationbarLeft />
    <PredictionOverlay />
  </div>
</template>

<script setup>
import MapView from '../components/Map.vue'
import NavigationbarLeft from '../components/NavigationbarLeft.vue'
import PredictionOverlay from '../components/PredictionOverlay.vue'
</script>

<style scoped>
.home {
  height: 100%;
  position: relative;
}
</style>