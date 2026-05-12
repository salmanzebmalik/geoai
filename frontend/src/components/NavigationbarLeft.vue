<template>
  <v-navigation-drawer permanent width="300" color="#1b2e1b">
     <v-list color="transparent">
          <v-list-item
            prepend-icon="mdi-numeric-1-circle"
            title="Select Area"
          ></v-list-item>
          <v-list-item
            prepend-icon="mdi-numeric-2-circle"
            title="Machine Learning Task"
          ></v-list-item>
          <v-list-item 
            prepend-icon="mdi-numeric-3-circle" 
            title="Start Analysis"
          ></v-list-item>
        </v-list>

        <v-btn @click="mapStore.triggerDrawing()" class="select-button">
            <v-icon left>mdi-select</v-icon>
            Select Area
          </v-btn>
        
  </v-navigation-drawer>
</template>

<script setup>
import { useMapStore } from '@/stores/map'

const mapStore = useMapStore()
</script>

<style scoped>
.select-button {
  width: 90%;
  margin: 0 16px;

  .v-icon {
    margin-right: 8px;
  }
}
</style>