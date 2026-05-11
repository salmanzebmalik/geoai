<template>
  <v-app>
    <v-app-bar>
      <div class="left-section">
        <v-icon icon="mdi-tree" color="green"></v-icon>
        <v-app-bar-title style="font-weight: bold;">
          GeoAI Tree Monitor
        </v-app-bar-title>
        <v-btn variant="text" to="/">Dashboard</v-btn>
        <v-btn variant="text" to="/about">About</v-btn>
      </div>
    </v-app-bar>

    <v-main>
      <RouterView />
    </v-main>
  </v-app>
</template>

<script setup>
import { RouterView } from 'vue-router'
</script>

<style>
.left-section {
  display: flex;
  align-items: center;
  margin-left: 20px;
}

.left-section .v-icon {
  margin-right: 10px;
}

.left-section .v-app-bar-title {
  margin-right: 20px;
}
</style>