<template>
  <div class="home">
    <!-- <MapOpenLayers /> -->
    <MapSentinel />
  </div>
</template>

<script setup>
import MapOpenLayers from '../components/MapOpenLayers.vue'
import MapSentinel from '../components/MapSentinel.vue'
</script>

<style scoped>
.home {
  height: 100%;
}
</style>