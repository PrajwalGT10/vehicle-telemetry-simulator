const map = L.map("map").setView([12.93, 77.61], 12);
const selectedLocalities = new Set();

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

let routeLayer = null;

// Load vehicles
fetch("data/vehicles.json")
  .then(r => r.json())
  .then(vehicles => {
    const select = document.getElementById("deviceSelect");
    Object.keys(vehicles).forEach(v => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });

    updateDeviceDetails(vehicles, select.value);
    populateDates(select.value);

    select.onchange = () => {
      updateDeviceDetails(vehicles, select.value);
      populateDates(select.value);
    };
  });

function updateDeviceDetails(vehicles, vehicleId) {
  const v = vehicles[vehicleId];
  document.getElementById("imei").textContent = v.imei;
  document.getElementById("vehicleName").textContent = v.vehicle_name;
  document.getElementById("equipmentType").textContent = v.equipment_type;
}

const startDateInput = document.getElementById("startDate");
const endDateInput = document.getElementById("endDate");

// Default demo dates
startDateInput.value = "2023-01-02";
endDateInput.value = "2023-01-04";


function loadRouteRange(vehicleId, startDate, endDate) {
  if (routeLayer) {
    map.removeLayer(routeLayer);
  }

  routeLayer = L.layerGroup().addTo(map);

  const dates = [];
  let current = new Date(startDate);
  const end = new Date(endDate);

  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10));
    current.setDate(current.getDate() + 1);
  }

  let bounds = [];

  dates.forEach(date => {
    const path = `../data/output/geojson/${vehicleId}/${date}_route.geojson`;

    fetch(path)
      .then(r => r.json())
      .then(data => {
        const layer = L.geoJSON(data, {
            style: {
            color: selectedLocalities.size > 0 ? "#f57c00" : "#1565c0",
            weight: 4,
            opacity: 0.8
        }
    });


        layer.addTo(routeLayer);
        bounds.push(layer.getBounds());
        map.fitBounds(L.latLngBounds(bounds));
      })
      .catch(() => {
        // Missing date file is OK in POC
        console.warn("No data for", date);
      });
  });
}

function reloadRoutes() {
  loadRouteRange(
    vehicleSelect.value,
    startDateInput.value,
    endDateInput.value
  );
}

const vehicleSelect = document.getElementById("deviceSelect");

vehicleSelect.addEventListener("change", () => {
  loadRouteRange(
    vehicleSelect.value,
    startDateInput.value,
    endDateInput.value
  );
});

startDateInput.addEventListener("change", () => {
  loadRouteRange(
    vehicleSelect.value,
    startDateInput.value,
    endDateInput.value
  );
});

endDateInput.addEventListener("change", () => {
  loadRouteRange(
    vehicleSelect.value,
    startDateInput.value,
    endDateInput.value
  );
});

// Initial load
loadRouteRange(
  vehicleSelect.value,
  startDateInput.value,
  endDateInput.value
);

const localitySelect = document.getElementById("localitySelect");
const selectedContainer = document.getElementById("selectedLocalities");

fetch("data/zones.geojson")
  .then(r => r.json())
  .then(data => {
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

  // Remove from dropdown
  [...localitySelect.options].forEach(o => {
    if (o.value === value) o.remove();
  });

  localitySelect.value = "";
  reloadRoutes();
});

function addLocalityTag(name) {
  const tag = document.createElement("div");
  tag.className = "tag";
  tag.dataset.name = name;
  tag.innerHTML = `${name} <span>×</span>`;

  tag.querySelector("span").onclick = () => {
    selectedLocalities.delete(name);
    tag.remove();

    // Re-add to dropdown
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    localitySelect.appendChild(opt);

    reloadRoutes();
  };

  selectedContainer.appendChild(tag);
}

