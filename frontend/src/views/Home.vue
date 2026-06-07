<template>
  <div class="home">
    <MapView />
    <NavigationbarLeft />
  </div>
</template>

<script setup>

import MapView from '../components/Map.vue'
import NavigationbarLeft from '../components/NavigationbarLeft.vue'

</script>

<style scoped>
.home {
  height: 100%;
}
</style>