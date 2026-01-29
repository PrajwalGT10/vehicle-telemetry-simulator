const map = L.map("map").setView([12.958319, 77.612422], 12);

let routeLayer = L.layerGroup().addTo(map);

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
    // Trigger initial update if val exists
    const initialVal = select.value;
    if (initialVal) {
      updateDetails(initialVal);
    }

    select.onchange = () => {
      reloadRoutes();
      updateDetails(select.value);
    };
  });

function updateDetails(imei) {
  const info = vehicleData[imei];
  if (info) {
    document.getElementById("imei").textContent = imei;
    document.getElementById("vehicleName").textContent = info.vehicle_name || "-";
    // Map vehicle_type to equipmentType field in UI
    document.getElementById("equipmentType").textContent = info.vehicle_type || info.equipment_type || "-";
  }
}

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
    const path = `../data/exported_geojson/${vName}/${date}.geojson`;
    fetch(path)
      .then(r => r.json())
      .then(data => {
        // Draw Points independently
        const layer = L.geoJSON(data, {
          pointToLayer: function (feature, latlng) {
            // Check for hybrid vs regular?
            // For now, uniform markers
            return L.circleMarker(latlng, {
              radius: 4,
              fillColor: "#ff7800",
              color: "#000",
              weight: 1,
              opacity: 1,
              fillOpacity: 0.8
            });
          },
          onEachFeature: function (feature, layer) {
            if (feature.properties) {
              layer.bindPopup(`
                     <b>Time:</b> ${feature.properties.timestamp}<br>
                     <b>Speed:</b> ${feature.properties.speed}<br>
                     <b>Heading:</b> ${feature.properties.heading}
                 `);
            }
          }
        });

        layer.addTo(routeLayer);
        bounds.push(layer.getBounds());

        if (bounds.length > 0) {
          const groupBounds = L.latLngBounds(bounds);
          if (groupBounds.isValid()) map.fitBounds(groupBounds);
        }
      })
      .catch(() => { });
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

// Compliance Report Logic
const btnReport = document.getElementById("btnGenerateReport");
const statusDiv = document.getElementById("reportStatus");
const linkReport = document.getElementById("reportLink");

if (btnReport) {
  btnReport.addEventListener("click", () => {
    // 1. UI State: Busy
    btnReport.disabled = true;
    statusDiv.textContent = "Generating Report... This may take a moment.";
    statusDiv.style.color = "#555";
    linkReport.style.display = "none";

    // 2. Call API
    fetch("/api/generate_report", { method: "POST" })
      .then(r => r.json())
      .then(data => {
        if (data.status === "success") {
          statusDiv.textContent = "Report Ready!";
          statusDiv.style.color = "green";

          linkReport.href = data.file_url;
          linkReport.style.display = "block";
          linkReport.textContent = "Download RA_12_Compliance_Report.csv";
        } else {
          statusDiv.textContent = "Error: " + data.message;
          statusDiv.style.color = "red";
        }
      })
      .catch(err => {
        statusDiv.textContent = "Request Failed: " + err;
        statusDiv.style.color = "red";
      })
      .finally(() => {
        btnReport.disabled = false;
      });
  });
}