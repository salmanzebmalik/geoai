<template>
  <div class="home">
    <MapView />
    <NavigationbarLeft />
    <LoadingOverlay />
  </div>
</template>

<script setup>
import MapView from '../components/Map.vue'
import NavigationbarLeft from '../components/NavigationbarLeft.vue'
import LoadingOverlay from '../components/LoadingOverlay.vue'
</script>

<style scoped>
.home {
  height: 100%;
  position: relative;
}
</style>