var map = L.map('map', {
    zoomControl: false
}).setView([27.69, 85.35], 12);

let flagMap = {}
var markers = {};
var currentTrail = null;
var selectedHex = null;
var aircraftInfoCache = {};
var photoCache = {};
var latestAircraftData = {};
var routeCache = {};
const weatherCache = {};

// Radar state
var isRadarMode = false;
var radarTileLayer = null;
var radarCircles = [];


var darkTileLayer = L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    {
        attribution: '© OpenStreetMap contributors © CARTO',
        maxZoom: 19
    }
);

var satelliteTileLayer = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {
        attribution: 'Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
        maxZoom: 19
    }
);


var radarBaseLayer = L.layerGroup();


var airportLabelsLayer = L.layerGroup().addTo(map);


var baseLayers = {
    "Dark"     : darkTileLayer,
    "Satellite": satelliteTileLayer,
    "Radar"    : radarBaseLayer
};



L.Control.BaseLayerDropdown = L.Control.extend({
    options: {
        position: 'topleft'
    },

    initialize: function (layers, options) {
        L.setOptions(this, options);
        this.layers = layers;          
        this.currentLayer = null;
    },

    onAdd: function (map) {
        this._map = map;

        const container = L.DomUtil.create('div', 'leaflet-control leaflet-bar custom-layer-dropdown');

 
        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(container, 'wheel', L.DomEvent.stopPropagation);

 
        const select = L.DomUtil.create('select', '', container);

        const optDefault = document.createElement('option');
        optDefault.value = '';
        optDefault.text = 'Map Style';
        optDefault.disabled = true;
        optDefault.selected = true;
        select.appendChild(optDefault);


        Object.keys(this.layers).forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.text = name;
            select.appendChild(option);
        });


        L.DomEvent.on(select, 'change', (e) => {
            const selectedName = e.target.value;
            if (!selectedName) return;

            const selectedLayer = this.layers[selectedName];

            if (this.currentLayer) {
                map.removeLayer(this.currentLayer);
            }


            selectedLayer.addTo(map);
            this.currentLayer = selectedLayer;

            if (selectedName === "Radar") {
                enterRadarMode();
            } else {
                exitRadarMode();
            }
        });


        const defaultLayer = this.layers["Dark"];
        if (defaultLayer) {
            defaultLayer.addTo(map);
            this.currentLayer = defaultLayer;
            select.value = "Dark";          
        }

        return container;
    }
});

const baseLayerDropdown = new L.Control.BaseLayerDropdown(baseLayers, {
    position: 'topleft'
}).addTo(map);


darkTileLayer.addTo(map);

const airportIcon = L.icon({
    iconUrl: '/static/airport.png',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -24]
});



const vnktGates = [
    ["1",27.6969972,85.3569389],
    ["2",27.6976056,85.3572167],
    ["3",27.6982139,85.3574944],
    ["4",27.6988222,85.3577694],
    ["5",27.6993722,85.35815],
    ["6",27.6998917,85.3583778],
    ["7",27.7003139,85.3585722],
    ["8",27.7007,85.3587472],
    ["9",27.7010861,85.3589222],
    ["10",27.7014417,85.3591806],
    ["11",27.7018,85.3593667],
    ["R1",27.6986111,85.3638889],
    ["R2",27.6991667,85.3636111],
    ["R3",27.6994444,85.3633333],
    ["R4",27.6997222,85.3633333]
];

vnktGates.forEach(g =>
    addTextLabel(g[0], g[1], g[2])
);


const airportMarker = L.marker([27.7005727, 85.3511981], { icon: airportIcon }).addTo(map);
airportMarker.bindPopup(`
    <b>Tribhuvan International Airport</b><br>
    <b>ICAO:</b> VNKT <br>
    <b>IATA:</b> KTM
`, { closeButton: false });


function kmhToKnots(kmh) {
    return kmh ? (kmh / 1.852).toFixed(0) : '—';
}


const photoPopup = document.createElement('div');
photoPopup.id = 'plane-photo-popup';
photoPopup.innerHTML = `
    <img id="popup-plane-img" style="max-width:260px; height:auto; border-radius:6px; border:1px solid #e67e22; display:block; margin-bottom:10px;">
    <div id="popup-route-info" style="margin-top:8px; line-height:1.4;"></div>
    <div id="popup-weather-info" style="margin-top:12px; padding-top:10px; border-top:1px solid #444; line-height:1.5; font-size:13px;">
        <strong style="color: #e67e22">Environment:</strong><br>
        <span id="weather-temp"></span><br>
        <span id="weather-pressure"></span><br>
        <span id="weather-wind"></span>
    </div>
`;
document.body.appendChild(photoPopup);

addTextLabel("RW02", 27.6838778, 85.3533889);
addTextLabel("RW20", 27.7051222, 85.3630667);


function addTextLabel(text, lat, lon) {
    L.marker([lat, lon], {
        icon: L.divIcon({
            className: 'label',
            html: text,
            iconSize: [60, 14],
            iconAnchor: [0, 0]
        }),
        interactive: false
    }).addTo(airportLabelsLayer);
}



function enterRadarMode() {
    if (isRadarMode) return;
    isRadarMode = true;

    map.removeLayer(darkTileLayer);
    map.removeLayer(satelliteTileLayer);
    map.removeLayer(airportLabelsLayer);


    if (!radarTileLayer) {
        radarTileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
            attribution: '© OpenStreetMap © CARTO',
            maxZoom: 19
        });
    }
    radarTileLayer.addTo(map);


    radarCircles.forEach(c => map.removeLayer(c));
    radarCircles = [];
    const center = [27.7005727, 85.3511981];
    [50, 100, 150].forEach(radiusKm => {
        const circle = L.circle(center, {
            color: '#0000ff',
            fill: false,
            weight: 2,
            opacity: 0.6,
            radius: radiusKm * 1000
        }).addTo(map);
        radarCircles.push(circle);
    });

    document.getElementById('map').classList.add('radar-mode');
    map.getContainer().style.backgroundColor = '#000000';
    map.getPane('tilePane').style.backgroundColor = '#000000';
    map.getPane('tilePane').style.opacity = '0';
    map.getPane('tilePane').style.visibility = 'hidden';

    map.setView(center, 8, { animate: false });
    map.dragging.disable();
    
}

function exitRadarMode() {
    if (!isRadarMode) return;
    isRadarMode = false;

    
    if (radarTileLayer) radarTileLayer.remove();
    radarCircles.forEach(c => map.removeLayer(c));
    radarCircles = [];

    
    darkTileLayer.addTo(map);
    airportLabelsLayer.addTo(map);


    document.getElementById('map').classList.remove('radar-mode');
    map.getPane('tilePane').style.opacity = '1';
    map.getPane('tilePane').style.visibility = 'visible';
    map.getPane('tilePane').style.backgroundColor = '';
    map.getContainer().style.backgroundColor = '';

    map.dragging.enable();
    map.setView([27.69, 85.35], 12, { animate: true });
}


map.on('baselayerchange', function(e) {
    if (e.name === "Radar") {
        enterRadarMode();
    } else {
        exitRadarMode();
    }
});

function fetchAircraftInfo(hex) {
    if (aircraftInfoCache.hasOwnProperty(hex)) {
        return Promise.resolve(aircraftInfoCache[hex]);
    }
    aircraftInfoCache[hex] = null;
    return fetch(`https://hexdb.io/api/v1/aircraft/${hex}`)
        .then(res => {
            if (!res.ok) throw new Error("No data");
            return res.json();
        })
        .then(info => {
            aircraftInfoCache[hex] = info && Object.keys(info).length ? info : null;
            return aircraftInfoCache[hex];
        })
        .catch(() => {
            aircraftInfoCache[hex] = null;
            return null;
        });
}

function fetchPlanePhoto(hex) {
    if (photoCache[hex] !== undefined) return Promise.resolve(photoCache[hex]);
    return fetch(`https://api.planespotters.net/pub/photos/hex/${hex.toUpperCase()}`)
        .then(res => {
            if (!res.ok) throw new Error('no photo');
            return res.json();
        })
        .then(data => {
            if (data.photos && data.photos.length > 0) {
                const photo = data.photos[0];
                const url = photo.thumbnail_large?.src || photo.thumbnail?.src || null;
                photoCache[hex] = url;
                return url;
            }
            photoCache[hex] = null;
            return null;
        })
        .catch(() => {
            photoCache[hex] = null;
            return null;
        });
}


function highlightRow(hex) {
    document.querySelectorAll('#aircraft-table tbody tr').forEach(r => r.classList.remove('active-plane'));
    const row = document.getElementById(`row-${hex}`);
    if (row) row.classList.add('active-plane');
}

function selectPlane(hex, centerMap = false) {
    if (currentTrail) {
        map.removeLayer(currentTrail);
        currentTrail = null;
    }
    if (selectedHex === hex) {
        selectedHex = null;
        highlightRow(null);
        photoPopup.style.display = 'none';
        document.getElementById('weather-temp').textContent = '';
        document.getElementById('weather-pressure').textContent = '';
        document.getElementById('weather-wind').textContent = '';
        return;
    }

    selectedHex = hex;
    highlightRow(hex);

    if (centerMap && markers[hex] && !isRadarMode) {
        map.flyTo(markers[hex].getLatLng(), 12, { duration: 0.7 });
    }

    const p = latestAircraftData[hex];
    const callsign = p?.callsign?.trim().toUpperCase() || '';

    photoPopup.style.display = 'block';

    const imgElement   = document.getElementById('popup-plane-img');
    const routeDiv     = document.getElementById('popup-route-info');
    const tempSpan     = document.getElementById('weather-temp');
    const pressureSpan = document.getElementById('weather-pressure');
    const windSpan     = document.getElementById('weather-wind');

    imgElement.style.display = 'none';
    routeDiv.innerHTML = '';
    tempSpan.textContent     = '';
    pressureSpan.textContent = '';
    windSpan.textContent     = '';

    fetchPlanePhoto(hex).then(url => {
        if (url) {
            imgElement.src = url;
            imgElement.style.display = 'block';
        }
    });

    if (callsign) {
        fetchRouteInfo(callsign).then(route => {
            if (route && route.origin && route.destination) {
                const origin = route.origin;
                const dest   = route.destination;
                routeDiv.innerHTML = `
                    <strong>Flight Route (${route.callsign_iata || callsign})</strong><br>
                    <strong>Airline:</strong> ${route.airline?.name || '—'}<br><br>
                    <strong>From:</strong><br>
                    ${origin.municipality || '—'} [${origin.country_iso_name || '—'}]<br>
                    ${origin.name || '—'}<br>
                    ${origin.iata_code || '—'} / ${origin.icao_code || '—'}
                    <br><br>
                    <strong>To:</strong><br>
                    ${dest.municipality || '—'} [${dest.country_iso_name || '—'}]<br>
                    ${dest.name || '—'} <br>
                    ${dest.iata_code || '—'} / ${dest.icao_code || '—'}
                `;
            } else {
                routeDiv.innerHTML = '';
            }
        }).catch(() => {
            routeDiv.innerHTML = '';
        });
    }

    if (p?.latitude && p?.longitude) {
        fetchWeather(p.latitude, p.longitude).then(w => {
            tempSpan.textContent     = `Air Temp     ${w.temp}`;
            pressureSpan.textContent = `Barometer   ${w.pressure}`;
            windSpan.textContent     = `Wind Speed  ${w.windSpeed} ${w.windDir ? 'from ' + w.windDir : ''}`;
        }).catch(() => {
            tempSpan.textContent     = 'Air Temp     —';
            pressureSpan.textContent = 'Barometer   —';
            windSpan.textContent     = 'Wind Speed  —';
        });
    }
}

function updateOrAddRow(hex, p, info) {
    let row = document.getElementById(`row-${hex}`);
    if (!row) {
        row = document.createElement('tr');
        row.id = `row-${hex}`;
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => selectPlane(hex, true));
        document.querySelector('#aircraft-table tbody').appendChild(row);
    }

    const registration = info.Registration?.trim() || '';
    const flag = registration ? getFlag(registration) : '';
    const regDisplay = flag 
        ? `${flag} ${registration}`
        : (registration || '—');

    row.innerHTML = `
        <td>${hex}</td>
        <td>${p.callsign || '—'}</td>
        <td>${parseFloat(p.altitude) || '—'}</td>
        <td>${p.ground_speed || '—'}</td>
        <td>${p.track || '—'}</td>
        <td>${p.latitude?.toFixed(5) || '—'}</td>
        <td>${p.longitude?.toFixed(5) || '—'}</td>
        <td>${parseFloat(p.vertical_rate) || '—'}</td>
        <td>${p.squawk || '—'}</td>
        <td>${p.alert || '—'}</td>
        <td>${p.emergency || '—'}</td>
        <td>${p.spi || '—'}</td>
        <td>${p.is_on_ground || '—'}</td>
        <td>${regDisplay}</td>                      <!-- ← here -->
        <td>${info.Manufacturer || '—'}</td>
        <td>${info.ICAOTypeCode || '—'}</td>
        <td>${info.Type || '—'}</td>
        <td>${info.RegisteredOwners || '—'}</td>
        <td>${info.OperatorFlagCode || '—'}</td>
        <td>${p.last_seen || "—"}</td>`;
}

function updateMapAndTable(data) {
    latestAircraftData = data.aircraft || {};

    Object.keys(latestAircraftData).forEach(hex => {
        const p = latestAircraftData[hex];

        fetchAircraftInfo(hex).then(info => {
            updateOrAddRow(hex, p, info || {});
        });

        if (!p.latitude || !p.longitude) return;

        const isOnGround = p.is_on_ground === "-1" || p.is_on_ground === -1;

        const icon = L.divIcon({
            className: 'plane-marker',
            html: `<img src="/static/plane-icon.png"
                style="width:28px; height:28px; transform-origin:center;
                       ${isOnGround ? 'filter: hue-rotate(45deg) saturate(5) brightness(1.3);' : ''}" />`,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });

        if (!markers[hex]) {
            markers[hex] = L.marker([p.latitude, p.longitude], { icon }).addTo(map);
            markers[hex].bindTooltip(p.callsign || hex.toUpperCase(), {
                permanent: false,
                direction: 'top',
                offset: [0, -12],
                opacity: 0.92,
                className: 'plane-tooltip'
            });

            markers[hex].on('click', () => selectPlane(hex, false));

            markers[hex].on('mouseover', function () {
                const img = this.getElement()?.querySelector('img');
                if (img) img.style.transform = 'scale(1.55)';
            });

            markers[hex].on('mouseout', function () {
                const img = this.getElement()?.querySelector('img');
                if (img) img.style.transform = 'scale(1)';
            });
        } else {
            markers[hex].setIcon(icon);
            markers[hex].setLatLng([p.latitude, p.longitude]);
            markers[hex].setTooltipContent(p.callsign || hex.toUpperCase());
        }

        const el = markers[hex].getElement();
        if (el && p.track != null) {
            const img = el.querySelector('img');
            if (img) img.style.transform = `rotate(${p.track}deg)`;
        }
    });


    Object.keys(markers).forEach(hex => {
        if (!latestAircraftData[hex]) {
            map.removeLayer(markers[hex]);
            delete markers[hex];
        }
    });

    if (selectedHex && latestAircraftData[selectedHex]) {
        const positions = latestAircraftData[selectedHex].positions || [];
        if (positions.length > 1) {
            const latLngs = positions.map(pos => [pos.lat, pos.lon]);
            if (currentTrail) {
                currentTrail.setLatLngs(latLngs);
            } else {
                currentTrail = L.polyline(latLngs, {
                    color: '#00ccff',
                    weight: 4,
                    opacity: 0.75,
                    lineCap: 'round',
                    smoothFactor: 1.2
                }).addTo(map);
            }
        }
    } else if (currentTrail) {
        map.removeLayer(currentTrail);
        currentTrail = null;
    }


    if (selectedHex && !latestAircraftData[selectedHex]) {
        photoPopup.style.display = 'none';
        selectedHex = null;
    }


    if (isRadarMode) {
        map.setView([27.7005727, 85.3511981], map.getZoom(), { animate: false });
    }
}


async function fetchWeather(lat, lon) {
    const key = `${lat.toFixed(5)}_${lon.toFixed(5)}`;
    if (weatherCache[key]) return weatherCache[key];

    try {
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,pressure_msl,wind_speed_10m,wind_direction_10m&timezone=auto`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Weather fetch failed');
        const data = await res.json();
        const w = data.current || {};

        const weather = {
            temp: w.temperature_2m != null ? `${w.temperature_2m.toFixed(2)} °C` : '—',
            pressure: w.pressure_msl != null ? `${w.pressure_msl.toFixed(1)} hPa` : '—',
            windSpeed: w.wind_speed_10m != null ? `${kmhToKnots(w.wind_speed_10m)} kts` : '—',
            windDir: w.wind_direction_10m != null ? `${Math.round(w.wind_direction_10m)}°` : '—'
        };

        weatherCache[key] = weather;
        return weather;
    } catch (err) {
        console.warn('Weather fetch error:', err);
        return { temp: '—', pressure: '—', windSpeed: '—', windDir: '—' };
    }
}

async function loadFlags() {
    try {
        const res = await fetch('https://plane.kushal-kc.com.np/api/flags');
        if (!res.ok) throw new Error("Failed to load flags");
        flagMap = await res.json();
        console.log(`Loaded ${Object.keys(flagMap).length} flag entries`);
    } catch (err) {
        console.error("Flags load failed:", err);
        flagMap = {}; // fallback to no flags
    }
}
loadFlags();

function getFlag(reg) {
    if (!reg || typeof reg !== 'string' || !reg.trim()) return '';

    const regUpper = reg.trim().toUpperCase();


    for (let len = 3; len >= 1; len--) {
        const prefix = regUpper.slice(0, len);
        if (flagMap[prefix]?.flag) {
            return flagMap[prefix].flag;
        }
    }
    return '';
}


function fetchRouteInfo(callsign) {
    if (!callsign || callsign.trim() === '') return Promise.resolve(null);
    callsign = callsign.trim().toUpperCase();

    if (routeCache[callsign]) return Promise.resolve(routeCache[callsign]);

    return fetch(`https://api.adsbdb.com/v0/callsign/${callsign}`)
        .then(res => {
            if (!res.ok) return null;
            return res.json();
        })
        .then(data => {
            const route = data?.response?.flightroute;
            if (route) {
                routeCache[callsign] = route;
                return route;
            }
            return null;
        })
        .catch(err => {
            console.error("Route fetch error:", err);
            return null;
        });
}


L.Control.View3DButton = L.Control.extend({
    options: { position: 'topleft' },
    onAdd: function(map) {
        const btn = L.DomUtil.create('button', 'view-3d-btn');
        btn.innerHTML = 'View in 3D (beta)';


        btn.style.backgroundColor = '#e67e22';
        btn.style.color = '#fff';
        btn.style.border = 'none';
        btn.style.padding = '8px 16px';
        btn.style.fontSize = '13px';
        btn.style.fontWeight = 'bold';
        btn.style.borderRadius = '6px';
        btn.style.cursor = 'pointer';
        btn.style.boxShadow = '0 2px 6px rgba(0,0,0,0.3)';

        btn.onmouseover = () => { btn.style.transform = 'scale(1.05)'; };
        btn.onmouseout  = () => { btn.style.transform = 'scale(1)'; };

        L.DomEvent.on(btn, 'click', () => {
            window.open('/3d', '_blank');
        });

        L.DomEvent.disableClickPropagation(btn);

        return btn;
    }
});

new L.Control.View3DButton().addTo(map);

function pollData() {
    fetch('/api/aircraft')
        .then(r => r.json())
        .then(updateMapAndTable)
        .catch(err => console.error("Poll error:", err));
}

setInterval(pollData, 1800);
pollData();   
