const map = L.map("map").setView([12.958319, 77.612422], 12);
const selectedLocalities = new Set();

let routeLayer = L.layerGroup().addTo(map);
let zoneLayer = L.layerGroup().addTo(map);
let allZonesData = null; 

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

// 1. Load Vehicles
let vehicleData = {};

fetch("data/vehicles.json")
  .then(r => r.json())
  .then(vehicles => {
    vehicleData = vehicles; // Store globally
    const select = document.getElementById("deviceSelect");
    Object.keys(vehicles).forEach(v => {
      const opt = document.createElement("option");
      opt.value = v; 
      // Show Name in Dropdown, but Value is IMEI
      opt.textContent = vehicles[v].vehicle_name || v; 
      select.appendChild(opt);
    });
    select.onchange = () => { reloadRoutes(); };
  });

// 2. Load Routes with Markers
function loadRouteRange(vehicleId, startDate, endDate) {
  routeLayer.clearLayers(); 
  const dates = [];
  let current = new Date(startDate);
  const end = new Date(endDate);

  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10));
    current.setDate(current.getDate() + 1);
  }

  const bounds = [];

  dates.forEach(date => {
    // Construct Path: ../data/exported_geojson/{VehicleName}/{Year}/{Month}/{Date}.geojson
    // Lookup vehicle name from global data
    const vInfo = vehicleData[vehicleId];
    if (!vInfo) return;
    
    // Ensure name format matches Export script (spaces to underscores etc if needed, 
    // but export script and UpdateUI should align on name from Config/Info).
    const vName = vInfo.vehicle_name; 
    
    const [year, month, day] = date.split("-");
    const path = `../data/exported_geojson/${vName}/${year}/${month}/${date}.geojson`;
    fetch(path)
      .then(r => r.json())
      .then(data => {
        // Draw Line
        const layer = L.geoJSON(data, {
            style: { color: "#1565c0", weight: 4 }
        });
        layer.addTo(routeLayer);
        bounds.push(layer.getBounds());

        // Draw Markers
        const coords = data.features[0].geometry.coordinates;
        if (coords.length > 0) {
            const startPt = [coords[0][1], coords[0][0]];
            const endPt = [coords[coords.length-1][1], coords[coords.length-1][0]];

            L.circleMarker(startPt, {
                color: 'green', fillColor: '#4CAF50', fillOpacity: 1, radius: 5
            }).addTo(routeLayer).bindPopup(`Start: ${date}`);

            L.circleMarker(endPt, {
                color: 'red', fillColor: '#F44336', fillOpacity: 1, radius: 5
            }).addTo(routeLayer).bindPopup(`End: ${date}`);
        }
        
        if (bounds.length > 0) {
             const groupBounds = L.latLngBounds(bounds);
             if (groupBounds.isValid()) map.fitBounds(groupBounds);
        }
      })
      .catch(() => {});
  });
}

function reloadRoutes() {
  const v = document.getElementById("deviceSelect").value;
  const s = document.getElementById("startDate").value;
  const e = document.getElementById("endDate").value;
  if (v) loadRouteRange(v, s, e);
}

document.getElementById("startDate").value = "2023-01-01";
document.getElementById("endDate").value = "2023-01-07";
document.getElementById("deviceSelect").addEventListener("change", reloadRoutes);
document.getElementById("startDate").addEventListener("change", reloadRoutes);
document.getElementById("endDate").addEventListener("change", reloadRoutes);

// Initial Load
setTimeout(reloadRoutes, 500);