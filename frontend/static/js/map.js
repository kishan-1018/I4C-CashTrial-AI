/**
 * Leaflet GIS Interactive Map Controller
 * Renders:
 * 1. Full Multi-Hop Trajectory from Victim Origin to Cash-Out Hotspot
 * 2. Victim Origin Pulsing Beacon Pin
 * 3. Transit Mule Layering Nodes (Hop 1, 2, ... N)
 * 4. Animated Inter-State Stolen Fund Flow Path
 * 5. Destination Hotspot Tactical Radius & Pulse
 * 6. Ranked Candidate Touchpoints (Bank ATMs, WLAs, CSP Mitras, Micro-ATMs)
 * 7. Live Tactical PCR Patrol Car Routing Animation
 */

class GISMapController {
  constructor(containerId = "map-container") {
    this.containerId = containerId;
    this.map = null;
    this.trajectoryLayer = null;
    this.corridorLayer = null;
    this.touchpointMarkersLayer = null;
    this.patrolMarker = null;
    this.patrolInterval = null;
  }

  init() {
    if (this.map) return;
    
    // Default pan-India central view
    this.map = L.map(this.containerId, {
      center: [22.5000, 78.9629],
      zoom: 5,
      zoomControl: true,
      attributionControl: false
    });

    // Dark Tactical Tile Layer (CartoDB Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd'
    }).addTo(this.map);

    this.trajectoryLayer = L.layerGroup().addTo(this.map);
    this.corridorLayer = L.layerGroup().addTo(this.map);
    this.touchpointMarkersLayer = L.layerGroup().addTo(this.map);
  }

  getTouchpointColor(type) {
    switch (type) {
      case "BANK_ATM": return "#00E5FF"; // Cyan
      case "WHITE_LABEL_ATM": return "#38BDF8"; // Light Blue
      case "CSP_BANK_MITRA": return "#00E676"; // Emerald Green
      case "MICRO_ATM_MERCHANT": return "#FFB300"; // Amber
      default: return "#94A3B8";
    }
  }

  /**
   * Main Dynamic Trajectory Renderer
   * Directly tracks user input: victim origin -> mule hops -> cash-out destination
   */
  renderFullTrajectory(trajectoryData) {
    if (!this.map) this.init();
    if (!trajectoryData) return;

    this.trajectoryLayer.clearLayers();
    this.corridorLayer.clearLayers();
    this.touchpointMarkersLayer.clearLayers();
    if (this.patrolInterval) clearInterval(this.patrolInterval);
    if (this.patrolMarker) this.map.removeLayer(this.patrolMarker);

    const origin = trajectoryData.origin || {};
    const hops = trajectoryData.transit_hops || [];
    const dest = trajectoryData.destination || {};
    const candidateTps = trajectoryData.candidate_touchpoints || [];
    const topTp = trajectoryData.top_touchpoint;

    const allRoutePoints = [];

    // 1. Render Victim Origin Beacon
    if (origin.coordinates && origin.coordinates[0] && origin.coordinates[1]) {
      allRoutePoints.push(origin.coordinates);

      const victimHtml = `
        <div class="victim-beacon-wrapper">
          <div class="victim-beacon-pulse"></div>
          <div class="victim-beacon-dot">🚨</div>
        </div>
      `;
      const victimIcon = L.divIcon({
        className: 'custom-victim-icon',
        html: victimHtml,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });

      const victimMarker = L.marker(origin.coordinates, { icon: victimIcon }).addTo(this.trajectoryLayer);
      victimMarker.bindPopup(`
        <div style="font-family: var(--font-sans, sans-serif); font-size: 11.5px; min-width: 190px; color: #0F172A;">
          <div style="font-weight: 700; color: #E11D48; display: flex; align-items: center; gap: 4px;">
            <span>🚨</span> VICTIM REPORT ORIGIN
          </div>
          <div style="font-weight: 600; font-size: 12px; margin-top: 3px;">${origin.district || ''}, ${origin.state || ''}</div>
          <hr style="margin: 4px 0; border: none; border-top: 1px solid #CBD5E1;"/>
          <b>Complaint ID:</b> ${origin.complaint_id || 'N/A'}<br/>
          <b>Amount Lost:</b> <span style="color: #E11D48; font-weight: 700;">₹${Number(origin.amount || 0).toLocaleString()}</span><br/>
          <b>Typology:</b> ${(origin.scam || '').replace(/_/g, ' ')}<br/>
          <b>Reporting Delay:</b> ${origin.delay_mins || 0} mins
        </div>
      `);
    }

    // 2. Render Transit Mule Layering Nodes
    hops.forEach((hop, idx) => {
      if (hop.coordinates && hop.coordinates[0] && hop.coordinates[1]) {
        allRoutePoints.push(hop.coordinates);

        const hopHtml = `
          <div style="
            background: #0284C7;
            color: white;
            font-size: 10px;
            font-weight: 700;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid white;
            box-shadow: 0 0 10px rgba(2, 132, 199, 0.8);
            cursor: pointer;
          ">#${hop.hop_number || idx + 1}</div>
        `;
        const hopIcon = L.divIcon({
          className: 'custom-hop-icon',
          html: hopHtml,
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        });

        const hopMarker = L.marker(hop.coordinates, { icon: hopIcon }).addTo(this.trajectoryLayer);
        hopMarker.bindPopup(`
          <div style="font-family: var(--font-sans, sans-serif); font-size: 11px; min-width: 180px; color: #0F172A;">
            <div style="font-weight: 700; color: #0284C7;">🔄 MULE LAYER HOP #${hop.hop_number || idx + 1}</div>
            <b>Bank:</b> ${hop.bank_name || 'Scheduled Commercial Bank'}<br/>
            <b>Branch City:</b> ${hop.branch_city || 'N/A'}, ${hop.branch_state || ''}<br/>
            <b>Account:</b> <code style="background: #F1F5F9; padding: 1px 4px; border-radius: 3px;">${hop.account || 'N/A'}</code><br/>
            <b>UTR:</b> ${hop.utr || 'N/A'}<br/>
            <b>Velocity:</b> ~${hop.velocity_mins || 5} mins to next hop
          </div>
        `);
      }
    });

    // 3. Render Destination Cash-Out Hotspot
    if (dest.coordinates && dest.coordinates[0] && dest.coordinates[1]) {
      allRoutePoints.push(dest.coordinates);

      // Outer radar circle
      L.circle(dest.coordinates, {
        color: '#00E5FF',
        fillColor: '#00E5FF',
        fillOpacity: 0.10,
        weight: 2,
        dashArray: '6, 6',
        radius: (dest.radius_km || 12) * 1000
      }).addTo(this.corridorLayer);

      // Inner danger core
      L.circle(dest.coordinates, {
        color: '#FF3D71',
        fillColor: '#FF3D71',
        fillOpacity: 0.22,
        weight: 1.5,
        radius: (dest.radius_km || 12) * 400
      }).addTo(this.corridorLayer);

      // Destination Flag Marker
      const destHtml = `
        <div style="
          background: #FF3D71;
          color: white;
          width: 28px;
          height: 28px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2px solid white;
          box-shadow: 0 0 14px #FF3D71;
          font-size: 13px;
        ">🎯</div>
      `;
      const destIcon = L.divIcon({
        className: 'custom-dest-icon',
        html: destHtml,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });

      const destMarker = L.marker(dest.coordinates, { icon: destIcon }).addTo(this.corridorLayer);
      destMarker.bindPopup(`
        <div style="font-family: var(--font-sans, sans-serif); font-size: 11.5px; min-width: 200px; color: #0F172A;">
          <div style="font-weight: 700; color: #E11D48;">🎯 PREDICTED CASH-OUT HOTSPOT</div>
          <div style="font-weight: 600; font-size: 12px;">${dest.corridor_name || 'Target Cashout Corridor'}</div>
          <div style="font-size: 10.5px; color: #64748B;">Jurisdiction: ${dest.state || 'Local State'}</div>
          <hr style="margin: 4px 0; border: none; border-top: 1px solid #CBD5E1;"/>
          <b>Confidence:</b> ${(Number(dest.confidence || 0.85) * 100).toFixed(1)}%<br/>
          <b>Radius:</b> ${dest.radius_km || 12} km tactical perimeter<br/>
          <b>Action:</b> Dispatched PCR patrol to high-risk touchpoint
        </div>
      `);
    }

    // 4. Draw Animated Inter-State Money Flow Trail
    if (allRoutePoints.length >= 2) {
      L.polyline(allRoutePoints, {
        color: '#00E5FF',
        weight: 6,
        opacity: 0.35,
        lineCap: 'round'
      }).addTo(this.trajectoryLayer);

      L.polyline(allRoutePoints, {
        color: '#00E5FF',
        weight: 3,
        opacity: 0.95,
        dashArray: '10, 10',
        className: 'animated-flow-trail'
      }).addTo(this.trajectoryLayer);
    }

    // 5. Render Candidate Touchpoints (ATMs / CSPs)
    this.renderTouchpoints(candidateTps);

    // 6. Animate Field Patrol Unit
    if (topTp && topTp.coordinates) {
      const unit = topTp.police_jurisdiction ? `PCR Unit (${topTp.police_jurisdiction.split(' ')[0]})` : "Tactical Patrol Unit";
      this.animatePatrolCar(topTp.coordinates, unit);
    }

    // 7. Auto-Fit Bounds & Smooth Fly-In
    if (allRoutePoints.length > 0) {
      const bounds = L.latLngBounds(allRoutePoints);
      this.map.fitBounds(bounds, { padding: [60, 60], maxZoom: 12 });

      if (dest.coordinates && allRoutePoints.length > 1) {
        setTimeout(() => {
          if (this.map) {
            this.map.flyTo(dest.coordinates, 12, { duration: 1.4 });
          }
        }, 2400);
      }
    }
  }

  renderCorridor(center, radiusKm, name, confidence = 0.79) {
    this.corridorLayer.clearLayers();
    
    const circle = L.circle(center, {
      color: '#00E5FF',
      fillColor: '#00E5FF',
      fillOpacity: 0.12,
      weight: 2,
      dashArray: '6, 6',
      radius: radiusKm * 1000
    }).addTo(this.corridorLayer);

    L.circle(center, {
      color: '#FF3D71',
      fillColor: '#FF3D71',
      fillOpacity: 0.25,
      weight: 1,
      radius: (radiusKm * 1000) * 0.4
    }).addTo(this.corridorLayer);

    circle.bindTooltip(`<b>${name}</b><br/>Confidence: ${(confidence * 100).toFixed(1)}%`, {
      permanent: true,
      direction: 'top',
      className: 'custom-leaflet-tooltip'
    });

    this.map.flyTo(center, 12, { duration: 1.2 });
  }

  renderTouchpoints(touchpoints) {
    this.touchpointMarkersLayer.clearLayers();

    touchpoints.forEach(tp => {
      const color = this.getTouchpointColor(tp.touchpoint_type);
      const isCCTV = tp.cctv_available;
      
      const iconHtml = `
        <div style="
          background: ${color};
          width: 14px;
          height: 14px;
          border-radius: 50%;
          border: 2px solid #0E1626;
          box-shadow: 0 0 10px ${color};
          cursor: pointer;
        "></div>
      `;

      const customIcon = L.divIcon({
        className: 'custom-tp-icon',
        html: iconHtml,
        iconSize: [14, 14]
      });

      const marker = L.marker(tp.coordinates, { icon: customIcon });
      
      const popupContent = `
        <div style="font-family: sans-serif; font-size: 11.5px; color: #0F172A; min-width: 180px;">
          <b style="color: #0369A1;">${tp.institution_name}</b><br/>
          <span style="font-size: 10px; color: #475569;">${tp.touchpoint_type.replace(/_/g, ' ')}</span><br/>
          <hr style="margin: 4px 0; border: none; border-top: 1px solid #E2E8F0;"/>
          <b>Jurisdiction:</b> ${tp.police_jurisdiction || 'N/A'}<br/>
          <b>Operating:</b> ${tp.operating_hours || '24x7'}<br/>
          <b>CCTV Available:</b> ${isCCTV ? '✅ YES (Sec 94 BNSS)' : '❌ NO'}<br/>
          <b>Patrol Distance:</b> ${tp.patrol_distance_km || '2.5'} km
        </div>
      `;
      marker.bindPopup(popupContent);
      this.touchpointMarkersLayer.addLayer(marker);
    });
  }

  animatePatrolCar(destCoords, unitName = "PCR Unit P-12") {
    if (this.patrolInterval) clearInterval(this.patrolInterval);
    if (this.patrolMarker) this.map.removeLayer(this.patrolMarker);

    const startLat = destCoords[0] - 0.025;
    const startLon = destCoords[1] - 0.025;

    const routeLine = L.polyline([[startLat, startLon], destCoords], {
      color: '#00E5FF',
      weight: 3,
      opacity: 0.8,
      dashArray: '8, 8'
    }).addTo(this.corridorLayer);

    const carHtml = `
      <div style="
        background: #FFB300;
        width: 20px;
        height: 20px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 2px solid white;
        box-shadow: 0 0 12px #FFB300;
        font-size: 11px;
      ">🚔</div>
    `;
    const carIcon = L.divIcon({ html: carHtml, iconSize: [20, 20] });
    this.patrolMarker = L.marker([startLat, startLon], { icon: carIcon }).addTo(this.map);
    this.patrolMarker.bindTooltip(`<b>${unitName}</b> (In Transit)`, { permanent: false, direction: 'top' });

    let step = 0;
    const totalSteps = 40;
    this.patrolInterval = setInterval(() => {
      step++;
      const currentLat = startLat + (destCoords[0] - startLat) * (step / totalSteps);
      const currentLon = startLon + (destCoords[1] - startLon) * (step / totalSteps);
      this.patrolMarker.setLatLng([currentLat, currentLon]);

      if (step >= totalSteps) {
        clearInterval(this.patrolInterval);
        this.patrolMarker.bindTooltip(`<b>${unitName}</b> (Arrived at Target Touchpoint)`, { permanent: true, direction: 'top' }).openTooltip();
      }
    }, 150);
  }
}

window.gisMap = new GISMapController();

