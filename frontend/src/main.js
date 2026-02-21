import { createApp } from 'vue'
import 'leaflet/dist/leaflet.css'
import './style.css'
import App from './App.vue'

// Fix Leaflet default marker icon paths broken by Vite's asset bundling
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

createApp(App).mount('#app')
