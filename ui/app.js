const map = L.map("map").setView([12.93, 77.61], 12);
const selectedLocalities = new Set();

// Layer Groups
let routeLayer = L.layerGroup().addTo(map);
let zoneLayer = L.layerGroup().addTo(map); // --- FIX: New layer for drawing zones ---

// Global variable to store zone data for lookup
let allZonesData = null; 

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

// 1. Load Vehicles
fetch("data/vehicles.json")
  .then(r => r.json())
  .then(vehicles => {
    const select = document.getElementById("deviceSelect");
    Object.keys(vehicles).forEach(v => {
      const opt = document.createElement("option");
      opt.value = v; // This is the IMEI
      opt.textContent = v;
      select.appendChild(opt);
    });

    if (select.value) {
        updateDeviceDetails(vehicles, select.value);
    }
    
    select.onchange = () => {
      updateDeviceDetails(vehicles, select.value);
      reloadRoutes();
    };
  });

function updateDeviceDetails(vehicles, vehicleId) {
  const v = vehicles[vehicleId];
  if (v) {
      document.getElementById("imei").textContent = v.imei;
      document.getElementById("vehicleName").textContent = v.vehicle_name;
      document.getElementById("equipmentType").textContent = v.equipment_type;
  }
}

// 2. Date Setup
const startDateInput = document.getElementById("startDate");
const endDateInput = document.getElementById("endDate");

// Default to a valid week in your dataset
startDateInput.value = "2023-01-01";
endDateInput.value = "2023-01-07";

// 3. Main Route Loader
function loadRouteRange(vehicleId, startDate, endDate) {
  routeLayer.clearLayers(); // Clear old routes

  const dates = [];
  let current = new Date(startDate);
  const end = new Date(endDate);

  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10));
    current.setDate(current.getDate() + 1);
  }

  let bounds = [];

  dates.forEach(date => {
    // --- FIX 1: Corrected Path & Filename ---
    // Was: `../data/output/geojson/${vehicleId}/${date}_route.geojson`
    // Now: `../data/exported_geojson/${vehicleId}/${date}.geojson`
    const path = `../data/exported_geojson/${vehicleId}/${date}.geojson`;

    fetch(path)
      .then(r => r.json())
      .then(data => {
        const layer = L.geoJSON(data, {
            style: {
            color: selectedLocalities.size > 0 ? "#f57c00" : "#1565c0",
            weight: 4,
            opacity: 0.8
        },
        onEachFeature: function (feature, layer) {
            // Optional: Add popup with date/distance info
            if (feature.properties) {
                layer.bindPopup(`Date: ${feature.properties.date}<br>Dist: ${feature.properties.distance_km} km`);
            }
        }
    });

        layer.addTo(routeLayer);
        bounds.push(layer.getBounds());
        
        // Only fit bounds if we have valid data
        if (bounds.length > 0) {
             const groupBounds = L.latLngBounds(bounds);
             if (groupBounds.isValid()) {
                map.fitBounds(groupBounds);
             }
        }
      })
      .catch(() => {
        console.warn("No data for", date);
      });
  });
}

function reloadRoutes() {
  const vehicleSelect = document.getElementById("deviceSelect");
  if (vehicleSelect.value) {
      loadRouteRange(
        vehicleSelect.value,
        startDateInput.value,
        endDateInput.value
      );
  }
}

// Event Listeners for Controls
document.getElementById("deviceSelect").addEventListener("change", reloadRoutes);
startDateInput.addEventListener("change", reloadRoutes);
endDateInput.addEventListener("change", reloadRoutes);


// 4. Localities / Zones Logic
const localitySelect = document.getElementById("localitySelect");
const selectedContainer = document.getElementById("selectedLocalities");

// Load Zones
fetch("data/zones.geojson")
  .then(r => r.json())
  .then(data => {
    allZonesData = data; // Store globally for lookup
    
    data.features.forEach(f => {
      const name = f.properties.name;
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      localitySelect.appendChild(opt);
    });
  });

localitySelect.addEventListener("change", () => {
  const value = localitySelect.value;
  if (!value || selectedLocalities.has(value)) return;

  selectedLocalities.add(value);
  addLocalityTag(value);
  
  // --- FIX 2: Actually draw the zone ---
  drawSelectedZones();

  // Remove from dropdown (UI polish)
  [...localitySelect.options].forEach(o => {
    if (o.value === value) o.remove();
  });

  localitySelect.value = "";
  reloadRoutes(); // To update route colors if you kept that logic
});

function addLocalityTag(name) {
  const tag = document.createElement("div");
  tag.className = "tag";
  tag.dataset.name = name;
  tag.innerHTML = `${name} <span>×</span>`;

  tag.querySelector("span").onclick = () => {
    selectedLocalities.delete(name);
    tag.remove();
    drawSelectedZones(); // Redraw (remove the deleted one)

    // Re-add to dropdown
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    localitySelect.appendChild(opt);

    reloadRoutes();
  };

  selectedContainer.appendChild(tag);
}

// --- FIX 2 Helper: Function to draw zones ---
function drawSelectedZones() {
    zoneLayer.clearLayers();
    
    if (!allZonesData) return;
    
    const zonesToShow = allZonesData.features.filter(f => 
        selectedLocalities.has(f.properties.name)
    );
    
    if (zonesToShow.length > 0) {
        const layer = L.geoJSON(zonesToShow, {
            style: {
                color: "#4caf50", // Green for zones
                weight: 2,
                fillOpacity: 0.1,
                dashArray: '5, 5'
            }
        });
        layer.addTo(zoneLayer);
        
        // Zoom to show the zones
        map.fitBounds(layer.getBounds());
    }
}

// Initial Kickoff
// (Added a small delay to ensure dropdown is populated)
setTimeout(reloadRoutes, 500);