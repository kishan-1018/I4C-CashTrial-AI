/**
 * Main Frontend Application Controller
 * Handles reactive UI state, WebSocket live streams, incident selection,
 * 4-tier explainability rendering, and statutory workflow triggers.
 * Now includes role-based view switching: Investigator, Victim, Admin.
 */

class DashboardApp {
  constructor() {
    this.currentIncidentId = null;
    this.currentAnalysis = null;
    this.incidents = [];
    this.socket = null;
    this.currentRole = "INVESTIGATOR";
    // Victim-specific state
    this.victimComplaints = [];
    this.selectedVictimComplaint = null;
    this._victimPollingTimers = {}; // complaint_id -> interval id
  }

  async init() {
    console.log("Initializing I4C Predictive Decision Support Dashboard...");
    if (window.gisMap) window.gisMap.init();
    if (window.muleGraph) window.muleGraph.init();

    this.bindEvents();
    this.bindVictimEvents();
    this.bindAdminEvents();
    await this.loadIncidents();
    await this.loadHeatmap();
    this.initWebSocket();
    this.loadAdminData();
  }

  // District suggestions keyed by state value — mirrors STATE_DEFAULT_DISTRICTS in generator.py
  get districtSuggestions() {
    return {
      "Andhra Pradesh": "Visakhapatnam", "Arunachal Pradesh": "Itanagar",
      "Assam": "Guwahati", "Bihar": "Patna", "Chhattisgarh": "Raipur",
      "Goa": "Panaji", "Gujarat": "Ahmedabad", "Haryana": "Gurugram",
      "Himachal Pradesh": "Shimla", "Jharkhand": "Ranchi", "Karnataka": "Bengaluru Urban",
      "Kerala": "Ernakulam", "Madhya Pradesh": "Indore", "Maharashtra": "Mumbai Suburban",
      "Manipur": "Imphal West", "Meghalaya": "East Khasi Hills", "Mizoram": "Aizawl",
      "Nagaland": "Kohima", "Odisha": "Khordha (Bhubaneswar)", "Punjab": "Ludhiana",
      "Rajasthan": "Jaipur", "Sikkim": "Gangtok", "Tamil Nadu": "Chennai",
      "Telangana": "Hyderabad", "Tripura": "West Tripura", "Uttar Pradesh": "Lucknow",
      "Uttarakhand": "Dehradun", "West Bengal": "Kolkata",
      "Delhi": "South Delhi", "Delhi NCR": "South Delhi",
      "Jammu & Kashmir": "Srinagar", "Ladakh": "Leh",
      "Chandigarh": "Chandigarh", "Puducherry": "Puducherry",
      "Dadra & Nagar Haveli": "Silvassa", "Daman & Diu": "Daman",
      "Lakshadweep": "Kavaratti", "Andaman & Nicobar Islands": "Port Blair",
    };
  }

  /* =========================================================
     ROLE-BASED VIEW SWITCHING
     ========================================================= */
  switchRole(role) {
    this.currentRole = role;
    // Hide all views
    document.querySelectorAll('.role-view').forEach(v => {
      v.style.display = 'none';
      v.classList.remove('active-view');
    });
    // Show the selected view
    const viewId = `view-${role.toLowerCase()}`;
    const viewEl = document.getElementById(viewId);
    if (viewEl) {
      viewEl.style.display = '';
      viewEl.classList.add('active-view');
      // Re-trigger fade animation
      viewEl.style.animation = 'none';
      viewEl.offsetHeight; // reflow
      viewEl.style.animation = '';
    }

    // Refresh data for the selected role
    if (role === 'VICTIM') {
      this.renderVictimComplaints();
    } else if (role === 'ADMIN') {
      this.loadAdminData();
    } else if (role === 'INVESTIGATOR') {
      // Re-invalidate map size after switching back
      setTimeout(() => {
        if (window.gisMap && window.gisMap.map) {
          window.gisMap.map.invalidateSize();
        }
      }, 100);
    }
  }

  bindEvents() {
    // Role selector
    const roleSelect = document.getElementById("user-role-select");
    if (roleSelect) {
      roleSelect.addEventListener("change", (e) => this.switchRole(e.target.value));
    }

    // Tab switching (Map vs Graph)
    document.getElementById("tab-map").addEventListener("click", () => this.switchCanvasView("map"));
    document.getElementById("tab-graph").addEventListener("click", () => this.switchCanvasView("graph"));

    // Filters
    document.getElementById("filter-state").addEventListener("change", () => this.applyFilters());
    document.getElementById("filter-typology").addEventListener("change", () => this.applyFilters());
    document.getElementById("filter-touchpoint").addEventListener("change", () => this.applyFilters());

    // Real-time Search Filter across complaints, UTRs, VPAs, districts
    const searchInput = document.getElementById("input-search");
    if (searchInput) {
      searchInput.addEventListener("input", () => this.applyFilters());
    }

    // Guided Tour Trigger
    document.getElementById("btn-run-tour").addEventListener("click", () => {
      if (this.currentRole !== 'INVESTIGATOR') {
        this.switchRole('INVESTIGATOR');
        document.getElementById("user-role-select").value = 'INVESTIGATOR';
      }
      if (window.caseTour) window.caseTour.startTour();
    });

    // Tour Stepper Controls
    document.getElementById("tour-btn-next").addEventListener("click", () => window.caseTour.nextStep());
    document.getElementById("tour-btn-prev").addEventListener("click", () => window.caseTour.prevStep());
    document.getElementById("tour-btn-close").addEventListener("click", () => window.caseTour.endTour());

    // Action Buttons
    document.getElementById("btn-approve-alert").addEventListener("click", () => this.approveTacticalAlert());
    document.getElementById("btn-prepare-req").addEventListener("click", () => this.prepareRequisitions());
    document.getElementById("btn-download-pdf").addEventListener("click", () => this.downloadDossierPdf());
    document.getElementById("btn-override").addEventListener("click", () => this.overrideLead());

    // Custom Intake & Corridor Tracking Modal triggers
    const btnOpenIntake = document.getElementById("btn-open-intake");
    if (btnOpenIntake) btnOpenIntake.addEventListener("click", () => {
      if (this.currentRole === 'VICTIM') {
        // If victim role is active, scroll to the report form instead
        document.querySelector('.victim-col-report')?.scrollIntoView({ behavior: 'smooth' });
      } else {
        this.openIntakeModal();
      }
    });
    
    const btnSimulateModal = document.getElementById("btn-simulate-modal");
    if (btnSimulateModal) btnSimulateModal.addEventListener("click", () => this.openIntakeModal());

    // Modal Close Controls
    const btnCloseModal = document.getElementById("btn-modal-close");
    if (btnCloseModal) btnCloseModal.addEventListener("click", () => this.closeIntakeModal());

    const btnCancelModal = document.getElementById("btn-modal-cancel");
    if (btnCancelModal) btnCancelModal.addEventListener("click", () => this.closeIntakeModal());

    const modalBackdrop = document.getElementById("modal-intake-backdrop");
    if (modalBackdrop) {
      modalBackdrop.addEventListener("click", (e) => {
        if (e.target === modalBackdrop) this.closeIntakeModal();
      });
    }

    // Citizen vs Officer Mode Switcher
    const btnModeVictim = document.getElementById("btn-mode-victim");
    const btnModeOfficer = document.getElementById("btn-mode-officer");
    const officerSection = document.getElementById("officer-advanced-section");
    if (btnModeVictim && btnModeOfficer && officerSection) {
      btnModeVictim.addEventListener("click", () => {
        btnModeVictim.classList.add("active");
        btnModeOfficer.classList.remove("active");
        officerSection.style.display = "none";
      });
      btnModeOfficer.addEventListener("click", () => {
        btnModeOfficer.classList.add("active");
        btnModeVictim.classList.remove("active");
        officerSection.style.display = "block";
      });
    }

    // Friendly Scam Typology Tiles
    document.querySelectorAll(".scam-tile").forEach(tile => {
      tile.addEventListener("click", () => {
        document.querySelectorAll(".scam-tile").forEach(t => t.classList.remove("active"));
        tile.classList.add("active");
        const scam = tile.getAttribute("data-scam");
        const sel = document.getElementById("modal-scam-category");
        if (sel) sel.value = scam;
      });
    });

    // Friendly Reporting Time Delay Pills
    document.querySelectorAll(".time-pill-btn").forEach(pill => {
      pill.addEventListener("click", () => {
        document.querySelectorAll(".time-pill-btn").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        const mins = parseInt(pill.getAttribute("data-mins")) || 25;
        const slider = document.getElementById("modal-delay-slider");
        if (slider) {
          slider.value = mins;
          slider.dispatchEvent(new Event("input"));
        }
      });
    });

    // Destination Mode Toggle (Auto-trace vs Custom suspect location)
    const destAuto = document.getElementById("dest-choice-auto");
    const destCustom = document.getElementById("dest-choice-custom");
    const customFields = document.getElementById("custom-dest-fields");
    if (destAuto && destCustom && customFields) {
      destAuto.addEventListener("change", () => {
        customFields.style.display = "none";
      });
      destCustom.addEventListener("change", () => {
        customFields.style.display = "grid";
      });
    }

    // District auto-fill when origin state changes
    const stateSelect = document.getElementById("modal-origin-state");
    const districtInput = document.getElementById("modal-origin-district");
    if (stateSelect && districtInput) {
      stateSelect.addEventListener("change", () => {
        const suggested = this.districtSuggestions[stateSelect.value];
        if (suggested) {
          districtInput.value = suggested;
          districtInput.style.color = "var(--cyan)";
          setTimeout(() => { districtInput.style.color = ""; }, 1500);
        }
      });
    }

    // Destination district auto-fill when destination state changes
    const destStateSelect = document.getElementById("modal-dest-state");
    const destDistrictInput = document.getElementById("modal-dest-district");
    if (destStateSelect && destDistrictInput) {
      destStateSelect.addEventListener("change", () => {
        const suggested = this.districtSuggestions[destStateSelect.value];
        if (suggested) {
          destDistrictInput.value = suggested;
          destDistrictInput.style.color = "var(--cyan)";
          setTimeout(() => { destDistrictInput.style.color = ""; }, 1500);
        }
      });
    }

    // Modal Delay Slider
    const delaySlider = document.getElementById("modal-delay-slider");
    const delayDisplay = document.getElementById("modal-delay-display");
    if (delaySlider && delayDisplay) {
      delaySlider.addEventListener("input", (e) => {
        const val = parseInt(e.target.value);
        if (val <= 20) {
          delayDisplay.textContent = `${val} mins (🚨 Golden Hour Critical Window)`;
          delayDisplay.style.color = "var(--coral)";
        } else if (val <= 45) {
          delayDisplay.textContent = `${val} mins (⚡ Golden Hour Priority Window)`;
          delayDisplay.style.color = "var(--cyan)";
        } else if (val <= 90) {
          delayDisplay.textContent = `${val} mins (⏳ Extended Withdrawal Window)`;
          delayDisplay.style.color = "var(--amber)";
        } else {
          delayDisplay.textContent = `${val} mins (⚠️ Delayed Reporting - Forensic Focus)`;
          delayDisplay.style.color = "var(--text-muted)";
        }
      });
    }

    // Random UTR Generator
    const btnRandomUtr = document.getElementById("btn-modal-random-utr");
    if (btnRandomUtr) {
      btnRandomUtr.addEventListener("click", () => {
        const utrInput = document.getElementById("modal-utr");
        if (utrInput) {
          utrInput.value = "4" + Math.floor(10000000000 + Math.random() * 90000000000);
        }
      });
    }

    // Quick Amount Buttons
    document.querySelectorAll(".btn-quick-amt").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".btn-quick-amt").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const val = btn.getAttribute("data-val");
        const amtInput = document.getElementById("modal-amount");
        if (amtInput) amtInput.value = val;
      });
    });

    // Preset Scenario Buttons
    document.querySelectorAll(".btn-preset").forEach(btn => {
      btn.addEventListener("click", () => {
        const presetKey = btn.getAttribute("data-preset");
        this.applyScenarioPreset(presetKey);
      });
    });

    // Mule hops selector display label
    const hopsSelect = document.getElementById("modal-num-hops");
    const hopsDisplay = document.getElementById("hops-display");
    if (hopsSelect && hopsDisplay) {
      const hopLabels = {"": "Auto", "1": "1 mule", "2": "2 mules", "3": "3 mules",
                        "4": "4 mules", "5": "5 mules", "6": "6 mules"};
      hopsSelect.addEventListener("change", () => {
        hopsDisplay.textContent = hopLabels[hopsSelect.value] || "Auto";
      });
    }

    // Modal Submit Trigger
    const btnSubmitModal = document.getElementById("btn-modal-submit");
    if (btnSubmitModal) {
      btnSubmitModal.addEventListener("click", () => this.submitCustomIncidentAndTrack());
    }
  }

  /* =========================================================
     VICTIM PORTAL — Event Bindings & Logic
     ========================================================= */
  bindVictimEvents() {
    // Scam chip selection
    document.querySelectorAll('.vp-scam-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.vp-scam-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
      });
    });

    // Time chip selection
    document.querySelectorAll('.vp-time-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.vp-time-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
      });
    });

    // Submit button
    const submitBtn = document.getElementById('victim-submit-btn');
    if (submitBtn) {
      submitBtn.addEventListener('click', () => this.submitVictimComplaint());
    }
  }

  async submitVictimComplaint() {
    const btn = document.getElementById('victim-submit-btn');
    const scamChip = document.querySelector('.vp-scam-chip.active');
    const scamCategory = scamChip ? scamChip.getAttribute('data-scam') : 'DIGITAL_ARREST';
    const amount = parseFloat(document.getElementById('victim-amount')?.value) || 350000;
    const state = document.getElementById('victim-state')?.value || 'Maharashtra';
    const district = document.getElementById('victim-district')?.value.trim() || 'Mumbai';
    const utr = document.getElementById('victim-utr')?.value.trim() || ("4289" + Math.floor(10000000 + Math.random() * 90000000));
    const timeChip = document.querySelector('.vp-time-chip.active');
    const delayMins = timeChip ? parseInt(timeChip.getAttribute('data-mins')) || 15 : 15;

    if (!amount || amount <= 0) {
      this.showToast("⚠️ Please enter a valid amount", "coral");
      return;
    }

    // Animated progress — now shows validation step
    const origText = btn.innerHTML;
    const steps = [
      `<span>🔍</span> Validating Transaction...`,
      `<span>🧠</span> AI Fraud Pattern Check...`,
      `<span>📍</span> Running Corridor Prediction...`,
      `<span>🛡️</span> Queuing for Investigator Review...`,
    ];
    let stepIdx = 0;
    btn.disabled = true;
    btn.innerHTML = steps[0];
    const timer = setInterval(() => {
      stepIdx = Math.min(stepIdx + 1, steps.length - 1);
      btn.innerHTML = steps[stepIdx];
    }, 500);

    try {
      const res = await fetch("/api/simulate-incident", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scam_category: scamCategory,
          disputed_amount_inr: amount,
          origin_state: state,
          origin_district: district,
          reporting_delay_minutes: delayMins,
          primary_utr: utr
        })
      });

      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const data = await res.json();
      const incident = data.incident;
      const validation = data.validation || {};
      const priorityScore = data.priority_score || 50;

      // Show validation result visually in victim UI
      const validationEl = document.getElementById('victim-validation-result');
      if (validationEl) {
        const isValid = validation.is_valid !== false;
        validationEl.style.display = 'block';
        validationEl.innerHTML = `
          <div style="padding:10px; border-radius:8px; border:1px solid ${isValid ? 'rgba(0,255,136,0.3)' : 'rgba(255,165,0,0.3)'}; background:${isValid ? 'rgba(0,255,136,0.05)' : 'rgba(255,165,0,0.05)'}; margin-bottom:10px;">
            <div style="font-size:11.5px; font-weight:700; color:${isValid ? 'var(--emerald)' : 'var(--amber)'}; margin-bottom:4px;">
              ${isValid ? '✅ Complaint Validated' : '⚠️ Validation Warnings'}
              <span style="float:right; font-family:var(--font-mono); font-size:11px;">Score: ${validation.validation_score || 80}/100</span>
            </div>
            <div style="font-size:11px; color:var(--text-primary);">${validation.validation_summary || 'Processing...'}</div>
            ${(validation.revision_hints || []).length > 0 ? `<ul style="margin:6px 0 0 14px; font-size:10.5px; color:var(--amber);">${(validation.revision_hints || []).map(h => `<li>${h}</li>`).join('')}</ul>` : ''}
          </div>
        `;
      }

      if (data.status === 'VALIDATION_FAILED') {
        this.showToast(`⚠️ Validation failed: ${validation.validation_summary}`, 'amber');
        return;
      }

      // Add to victim complaints
      this.victimComplaints.unshift({
        complaint_id: incident.complaint_id,
        scam_category: scamCategory,
        disputed_amount_inr: amount,
        origin_state: state,
        origin_district: district,
        reporting_delay_minutes: delayMins,
        primary_utr: utr,
        filed_at: new Date().toISOString(),
        status: 'FILED',
        workflow_stage: data.workflow_stage || 'PENDING_REVIEW',
        priority_score: priorityScore,
        decision_support: data.decision_support,
        validation: validation,
        incident: incident
      });

      // Also add to global incidents for investigator view
      this.incidents.unshift(incident);
      this.renderIncidentList(this.incidents);

      this.renderVictimComplaints();
      // Auto-select the new complaint to show timeline
      this.selectedVictimComplaint = incident.complaint_id;
      this.renderVictimComplaints();
      this.startVictimTimlinePolling(incident.complaint_id);

      this.showToast(
        `✅ Complaint ${incident.complaint_id} validated & submitted! Priority Score: ${priorityScore}/100. Under Investigator review.`,
        "emerald"
      );

    } catch (e) {
      this.showToast(`❌ ${e.message || "Failed to submit complaint"}`, "coral");
    } finally {
      clearInterval(timer);
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }

  renderVictimComplaints() {
    const listEl = document.getElementById('victim-complaints-list');
    if (!listEl) return;

    if (this.victimComplaints.length === 0) {
      listEl.innerHTML = `
        <div class="vp-empty-state">
          <span style="font-size: 32px;">📭</span>
          <p>No complaints filed yet. Use the form on the left to report a fraud.</p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = '';
    this.victimComplaints.forEach((c, idx) => {
      // Simulate evolving status based on time elapsed
      const elapsed = (Date.now() - new Date(c.filed_at).getTime()) / 1000;
      let status = 'FILED';
      let statusClass = 'vp-status-filed';
      let statusText = '📋 Complaint Filed';
      if (elapsed > 8) { status = 'INVESTIGATING'; statusClass = 'vp-status-investigating'; statusText = '🔍 Under Investigation'; }
      if (elapsed > 20) { status = 'ACTION_TAKEN'; statusClass = 'vp-status-action'; statusText = '🛡️ Action Taken'; }
      if (elapsed > 45) { status = 'RESOLVED'; statusClass = 'vp-status-resolved'; statusText = '✅ Resolved'; }
      c.status = status;

      const card = document.createElement('div');
      card.className = `vp-complaint-card ${this.selectedVictimComplaint === c.complaint_id ? 'selected' : ''}`;
      card.innerHTML = `
        <div class="vp-complaint-top">
          <span class="vp-complaint-id">${c.complaint_id}</span>
          <span class="vp-status ${statusClass}">${statusText}</span>
        </div>
        <div class="vp-complaint-amount">₹${Number(c.disputed_amount_inr).toLocaleString()}</div>
        <div class="vp-complaint-meta">
          <span>${c.scam_category.replace(/_/g, ' ')}</span>
          <span>${c.origin_district}, ${c.origin_state}</span>
        </div>
      `;
      card.addEventListener('click', () => {
        this.selectedVictimComplaint = c.complaint_id;
        this.renderVictimComplaints();
        this.renderVictimTimeline(c);
      });
      listEl.appendChild(card);
    });
  }

  renderVictimTimeline(complaint) {
    const el = document.getElementById('victim-timeline');
    if (!el) return;

    // If we have live timeline events from the backend, prefer those
    const liveEvents = complaint.timeline_events_live;
    if (liveEvents && liveEvents.length > 0) {
      el.innerHTML = '';
      liveEvents.forEach(evt => {
        const item = document.createElement('div');
        const stateClass = evt.status === 'completed' ? 'completed'
          : evt.status === 'active' ? 'active'
          : evt.status === 'warning' ? 'active'
          : evt.status === 'failed' ? 'active'
          : 'pending';
        item.className = `vp-timeline-item ${stateClass}`;
        item.innerHTML = `
          <div class="vp-timeline-dot">${evt.icon || '📋'}</div>
          <div class="vp-timeline-content">
            <div class="vp-timeline-title">${evt.stage}</div>
            <div class="vp-timeline-desc">${evt.desc}</div>
            <div class="vp-timeline-time">${new Date(evt.time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} IST</div>
          </div>
        `;
        el.appendChild(item);
      });

      // Show revision hints if any
      if (complaint.revision_hints && complaint.revision_hints.length > 0) {
        const hintsDiv = document.createElement('div');
        hintsDiv.style.cssText = 'background:rgba(255,165,0,0.08);border:1px solid rgba(255,165,0,0.3);border-radius:8px;padding:10px 12px;margin-top:10px;';
        hintsDiv.innerHTML = `
          <div style="font-size:11px;font-weight:700;color:var(--amber);margin-bottom:6px;">⚠️ Revision Hints — Please address these:</div>
          <ul style="margin:0;padding-left:16px;">
            ${complaint.revision_hints.map(h => `<li style="font-size:11px;color:var(--text-primary);margin-bottom:3px;">${h}</li>`).join('')}
          </ul>
        `;
        el.appendChild(hintsDiv);
      }
      return;
    }

    // Fallback: generate timeline from complaint data (for just-submitted complaints before first poll)
    const elapsed = (Date.now() - new Date(complaint.filed_at).getTime()) / 1000;
    const ds = complaint.decision_support;
    const corridor = ds?.taxonomy?.predicted?.primary_corridor?.name || 'Target Corridor';
    const eta = ds?.taxonomy?.predicted?.estimated_patrol_eta || '8-12 mins';
    const filedTime = new Date(complaint.filed_at);
    const validationScore = complaint.validation?.validation_score || 80;
    const isValid = complaint.validation?.is_valid !== false;

    const timelineSteps = [
      {
        stage: "Complaint Filed via NCRP 1930",
        desc: `Complaint ${complaint.complaint_id} registered. Amount: ₹${Number(complaint.disputed_amount_inr).toLocaleString()}. Category: ${complaint.scam_category.replace(/_/g, ' ')}.`,
        time: filedTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: '📋', status: 'completed'
      },
      {
        stage: "AI Validation Check",
        desc: isValid
          ? `✅ Transaction verified & fraud pattern confirmed. Validation score: ${validationScore}/100.`
          : `⚠️ Validation warnings detected (score: ${validationScore}/100). Review hints below.`,
        time: new Date(filedTime.getTime() + 1000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: isValid ? '✅' : '⚠️', status: elapsed > 2 ? 'completed' : 'active'
      },
      {
        stage: "AI Analysis & Corridor Prediction",
        desc: `Machine learning model identified primary cash-out corridor: ${corridor}. Confidence: ${ds?.taxonomy?.predicted?.primary_corridor?.confidence ? (ds.taxonomy.predicted.primary_corridor.confidence * 100).toFixed(1) + '%' : '82%'}.`,
        time: new Date(filedTime.getTime() + 2000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: '🧠', status: elapsed > 3 ? 'completed' : 'active'
      },
      {
        stage: "Under Investigator Review",
        desc: `Complaint forwarded to authorized investigator. Awaiting human review and approval before alerts are dispatched. Priority Score: ${complaint.priority_score || 50}/100.`,
        time: new Date(filedTime.getTime() + 3000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: '👮', status: elapsed > 5 ? 'completed' : 'active'
      },
      {
        stage: "Bank Freeze Alert Dispatched",
        desc: `Freeze alerts sent to beneficiary banks via CFCFRMS. Target accounts flagged for immediate hold.`,
        time: new Date(filedTime.getTime() + 5000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: '🏦', status: elapsed > 8 ? 'completed' : elapsed > 5 ? 'active' : 'pending'
      },
      {
        stage: "LEA Tactical Alert Dispatched",
        desc: `Inter-state coordination alert dispatched to destination jurisdiction via I4C Samanvay. Patrol unit ETA: ${eta}.`,
        time: new Date(filedTime.getTime() + 10000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: '🚔', status: elapsed > 15 ? 'completed' : elapsed > 8 ? 'active' : 'pending'
      },
      {
        stage: "Field Unit Deployed to Cash-Out Point",
        desc: `PCR patrol unit dispatched to predicted cash-out touchpoint in ${corridor}. CCTV preservation notice issued under Sec 94 BNSS.`,
        time: new Date(filedTime.getTime() + 18000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: '📍', status: elapsed > 25 ? 'completed' : elapsed > 15 ? 'active' : 'pending'
      },
      {
        stage: "Investigation Complete — Case Resolved",
        desc: `Suspected mule accounts frozen. Evidence preserved. FIR copy and forensic dossier available for download.`,
        time: new Date(filedTime.getTime() + 30000).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        icon: '✅', status: elapsed > 45 ? 'completed' : elapsed > 25 ? 'active' : 'pending'
      }
    ];

    el.innerHTML = '';
    timelineSteps.forEach(step => {
      const item = document.createElement('div');
      item.className = `vp-timeline-item ${step.status}`;
      item.innerHTML = `
        <div class="vp-timeline-dot">${step.icon}</div>
        <div class="vp-timeline-content">
          <div class="vp-timeline-title">${step.stage}</div>
          <div class="vp-timeline-desc">${step.desc}</div>
          <div class="vp-timeline-time">${step.time} IST</div>
        </div>
      `;
      el.appendChild(item);
    });
  }

  /* =========================================================
     ADMIN CONSOLE — Event Bindings & Logic
     ========================================================= */
  bindAdminEvents() {
    const addUserBtn = document.getElementById('admin-add-user-btn');
    if (addUserBtn) {
      addUserBtn.addEventListener('click', () => {
        this.showToast("👤 User creation form would open here (demo mode)", "cyan");
      });
    }
  }

  async loadAdminData() {
    this.renderAdminIngestionLog();
    this.renderAdminUsers();
    this.renderAdminMetrics();
    this.animateGauges();
  }

  renderAdminMetrics() {
    // Update ingestion summary counts
    const totalIngested = this.incidents.length + 48291;
    document.getElementById('admin-total-ingested').textContent = totalIngested.toLocaleString();
    document.getElementById('admin-processed').textContent = (totalIngested - 23).toLocaleString();
    document.getElementById('admin-failed').textContent = '23';
    document.getElementById('admin-pending').textContent = '7';
  }

  animateGauges() {
    // Animate SVG gauge fills on load
    document.querySelectorAll('.gauge-fill').forEach(gauge => {
      const target = gauge.getAttribute('stroke-dashoffset');
      gauge.setAttribute('stroke-dashoffset', '314');
      setTimeout(() => {
        gauge.style.transition = 'stroke-dashoffset 1.5s ease';
        gauge.setAttribute('stroke-dashoffset', target);
      }, 200);
    });
  }

  renderAdminIngestionLog() {
    const tbody = document.getElementById('admin-ingestion-tbody');
    if (!tbody) return;

    const now = new Date();
    const events = [
      { time: new Date(now - 120000), type: 'NCRP 1930 Feed Sync', source: 'NCRP Gateway API', records: 47, status: 'success', detail: 'Pan-India live complaint feed synchronized' },
      { time: new Date(now - 300000), type: 'Touchpoint Registry Update', source: 'RBI ATM Database', records: 1284, status: 'success', detail: 'ATM/CSP/WLA coordinate refresh (12 corridors)' },
      { time: new Date(now - 600000), type: 'Model Retraining Job', source: 'ML Pipeline v2.4.1', records: 48291, status: 'success', detail: 'Ensemble (RF+XGB+LGBM) retrained on latest data' },
      { time: new Date(now - 1200000), type: 'Bank Freeze Webhook', source: 'CFCFRMS Integration', records: 12, status: 'success', detail: 'Freeze confirmations received for flagged accounts' },
      { time: new Date(now - 1800000), type: 'Duplicate Detection', source: 'Dedup Engine', records: 3, status: 'pending', detail: 'Potential duplicate complaints flagged for review' },
      { time: new Date(now - 2400000), type: 'NCRP 1930 Feed Sync', source: 'NCRP Gateway API', records: 38, status: 'success', detail: 'Scheduled 15-min sync completed' },
      { time: new Date(now - 3600000), type: 'GIS Heatmap Recalc', source: 'Spatial Analysis Engine', records: 892, status: 'success', detail: 'Risk corridor polygons regenerated (12 zones)' },
      { time: new Date(now - 5400000), type: 'Data Quality Check', source: 'Validation Pipeline', records: 5, status: 'error', detail: '5 records rejected: missing UTR / invalid amount' },
      { time: new Date(now - 7200000), type: 'Audit Trail Export', source: 'Compliance Module', records: 2410, status: 'success', detail: 'SHA-256 tamper-evident log exported to cold storage' },
      { time: new Date(now - 9000000), type: 'Feature Engineering', source: 'ML Pipeline v2.4.1', records: 23, status: 'success', detail: '23 engineered features recalculated for new data' },
    ];

    tbody.innerHTML = '';
    events.forEach(evt => {
      const statusClass = evt.status === 'success' ? 'admin-status-success' : evt.status === 'error' ? 'admin-status-error' : 'admin-status-pending';
      const statusLabel = evt.status === 'success' ? '✓ Success' : evt.status === 'error' ? '✗ Failed' : '⏳ Pending';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);">${evt.time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
        <td style="font-weight: 600; color: var(--text-primary);">${evt.type}</td>
        <td>${evt.source}</td>
        <td style="font-family: var(--font-mono); font-weight: 600; color: var(--cyan);">${evt.records.toLocaleString()}</td>
        <td><span class="admin-status-pill ${statusClass}">${statusLabel}</span></td>
        <td style="font-size: 11px; max-width: 250px;">${evt.detail}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  renderAdminUsers() {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;

    const users = [
      { id: 'KA_8841', name: 'Inspector Rajesh Kumar', role: 'investigator', jurisdiction: 'Karnataka Cyber Crime PS', lastActive: '2 mins ago', active: true },
      { id: 'MH_4422', name: 'SI Priya Deshmukh', role: 'investigator', jurisdiction: 'Maharashtra Cyber Cell, Mumbai', lastActive: '5 mins ago', active: true },
      { id: 'DL_1203', name: 'ACP Vikram Singh', role: 'investigator', jurisdiction: 'Delhi NCR Special Cell', lastActive: '12 mins ago', active: true },
      { id: 'HR_7761', name: 'Inspector Anil Sharma', role: 'investigator', jurisdiction: 'Haryana Nuh District PS', lastActive: '1 hour ago', active: true },
      { id: 'ADMIN_001', name: 'Suresh Rajan (Super Admin)', role: 'admin', jurisdiction: 'I4C HQ, New Delhi', lastActive: 'Now', active: true },
      { id: 'ADMIN_002', name: 'Kavitha Nair (Ops)', role: 'admin', jurisdiction: 'I4C Data Operations', lastActive: '30 mins ago', active: true },
      { id: 'ANALYST_01', name: 'Dr. Meera Krishnan', role: 'analyst', jurisdiction: 'ML & Analytics Division', lastActive: '15 mins ago', active: true },
      { id: 'TN_9921', name: 'Inspector Arjun Ravi', role: 'investigator', jurisdiction: 'Tamil Nadu Cyber Crime', lastActive: '3 hours ago', active: false },
      { id: 'WB_3301', name: 'SI Debabrata Roy', role: 'investigator', jurisdiction: 'West Bengal Cyber Crime', lastActive: '1 day ago', active: false },
      { id: 'CIT_10001', name: 'Ramesh Gupta (Victim)', role: 'victim', jurisdiction: 'Mumbai, Maharashtra', lastActive: '20 mins ago', active: true },
    ];

    tbody.innerHTML = '';
    users.forEach(user => {
      const roleClass = `admin-role-${user.role}`;
      const roleLabel = user.role.charAt(0).toUpperCase() + user.role.slice(1);
      const statusClass = user.active ? 'admin-status-active' : 'admin-status-inactive';
      const statusLabel = user.active ? '● Active' : '○ Inactive';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-weight: 600; color: var(--cyan); font-size: 11px;">${user.id}</td>
        <td style="font-weight: 600; color: var(--text-primary);">${user.name}</td>
        <td><span class="admin-role-badge ${roleClass}">${roleLabel}</span></td>
        <td style="font-size: 11px;">${user.jurisdiction}</td>
        <td style="font-size: 11px; color: ${user.active ? 'var(--emerald)' : 'var(--text-muted)'};">${user.lastActive}</td>
        <td><span class="admin-status-pill ${statusClass}">${statusLabel}</span></td>
        <td>
          <input type="checkbox" class="admin-toggle" ${user.active ? 'checked' : ''} title="Toggle user active status">
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Bind toggle events
    tbody.querySelectorAll('.admin-toggle').forEach((toggle, idx) => {
      toggle.addEventListener('change', () => {
        const user = users[idx];
        const newState = toggle.checked ? 'activated' : 'deactivated';
        this.showToast(`👤 User ${user.id} (${user.name}) ${newState}`, toggle.checked ? 'emerald' : 'amber');
      });
    });
  }


  /* =========================================================
     INVESTIGATOR VIEW — Existing Logic (preserved)
     ========================================================= */
  switchCanvasView(view) {
    const mapEl = document.getElementById("map-container");
    const graphEl = document.getElementById("graph-container");
    const tabMap = document.getElementById("tab-map");
    const tabGraph = document.getElementById("tab-graph");

    if (view === "map") {
      mapEl.style.display = "block";
      graphEl.style.display = "none";
      tabMap.classList.add("active");
      tabGraph.classList.remove("active");
    } else {
      mapEl.style.display = "none";
      graphEl.style.display = "block";
      tabMap.classList.remove("active");
      tabGraph.classList.add("active");
      if (this.currentAnalysis && window.muleGraph) {
        window.muleGraph.render(this.currentAnalysis.network_graph);
      }
    }
  }

  async loadIncidents() {
    try {
      const res = await fetch("/api/recent-incidents");
      const data = await res.json();
      this.incidents = data.incidents || [];
      this.renderIncidentList(this.incidents);

      if (this.incidents.length > 0 && !this.currentIncidentId) {
        this.selectIncident(this.incidents[0].complaint_id);
      }
    } catch (e) {
      console.error("Failed to load incidents", e);
    }
  }

  renderIncidentList(incidents) {
    const listEl = document.getElementById("incident-list");
    listEl.innerHTML = "";

    // Sort by priority_score descending (higher score = more urgent)
    const sorted = [...incidents].sort((a, b) => {
      const sa = a._validation?.priority_score || a.priority_score || 0;
      const sb = b._validation?.priority_score || b.priority_score || 0;
      return sb - sa;
    });

    sorted.forEach(inc => {
      const card = document.createElement("div");
      card.className = `incident-card ${inc.complaint_id === this.currentIncidentId ? 'active' : ''}`;
      card.id = `card-${inc.complaint_id}`;
      
      const delay = inc.reporting_delay_minutes || 0;
      let badgeClass = "badge-forensic";
      let badgeText = "FORENSIC";
      if (delay <= 45) { badgeClass = "badge-high"; badgeText = "HIGH PRIORITY"; }
      else if (delay <= 180) { badgeClass = "badge-medium"; badgeText = "MEDIUM"; }

      // Validation status icon
      const val = inc._validation || {};
      const isValidated = val.is_valid !== false;
      const validScore = val.validation_score || 80;
      const validIcon = isValidated ? '✅' : '⚠️';

      // Workflow stage chip colour
      const wfMeta = this._workflowStageStyle(inc._workflowStage || 'PENDING_REVIEW');

      card.innerHTML = `
        <div class="incident-card-top">
          <span class="incident-id">${inc.complaint_id}</span>
          <span class="badge-priority ${badgeClass}">${badgeText}</span>
        </div>
        <div class="incident-amount">INR ${inc.disputed_amount_inr.toLocaleString()}</div>
        <div class="incident-meta">
          <span>${inc.scam_category.replace(/_/g, ' ')}</span>
          <span>${delay}m delay</span>
        </div>
        <div style="display:flex;gap:6px;margin-top:5px;align-items:center;flex-wrap:wrap;">
          <span style="font-size:10px;font-family:var(--font-mono);background:rgba(0,229,255,0.12);color:var(--cyan);padding:2px 6px;border-radius:8px;font-weight:700;">⭐ ${inc._priorityScore || validScore > 70 ? Math.min(95, validScore) : 55}/100</span>
          <span style="font-size:10px;color:${isValidated ? 'var(--emerald)' : 'var(--amber)'}">${validIcon} ${isValidated ? 'Validated' : 'Flagged'}</span>
          <span style="font-size:9.5px;padding:1px 6px;border-radius:8px;${wfMeta.style}">${wfMeta.label}</span>
        </div>
      `;

      card.addEventListener("click", () => this.selectIncident(inc.complaint_id));
      listEl.appendChild(card);
    });
  }

  _workflowStageStyle(stage) {
    const map = {
      'PENDING_REVIEW':       { label: '📋 Pending Review',    style: 'background:rgba(0,229,255,0.1);color:var(--cyan);' },
      'UNDER_REVIEW':         { label: '👮 Under Review',      style: 'background:rgba(255,165,0,0.1);color:var(--amber);' },
      'APPROVED':             { label: '✅ Approved',          style: 'background:rgba(0,255,136,0.1);color:var(--emerald);' },
      'ALERTS_DISPATCHED':    { label: '🚔 Alerts Sent',       style: 'background:rgba(0,255,136,0.12);color:var(--emerald);font-weight:700;' },
      'REJECTED':             { label: '🔄 Re-validating',     style: 'background:rgba(255,61,113,0.1);color:var(--coral);' },
      'RE_VALIDATING':        { label: '🔄 Re-validating',     style: 'background:rgba(255,61,113,0.1);color:var(--coral);' },
      'REVISION_REQUESTED':   { label: '⚠️ Revision Req.',    style: 'background:rgba(255,165,0,0.1);color:var(--amber);' },
      'PERMANENTLY_REJECTED': { label: '❌ Rejected',          style: 'background:rgba(255,61,113,0.08);color:var(--coral);' },
      'VALIDATION_FAILED':    { label: '⚠️ Val. Failed',      style: 'background:rgba(255,165,0,0.1);color:var(--amber);' },
    };
    return map[stage] || { label: '📋 In Queue', style: 'background:rgba(0,229,255,0.08);color:var(--cyan);' };
  }

  async selectIncident(complaintId) {
    this.currentIncidentId = complaintId;

    // Highlight card in list
    document.querySelectorAll(".incident-card").forEach(c => c.classList.remove("active"));
    const activeCard = document.getElementById(`card-${complaintId}`);
    if (activeCard) activeCard.classList.add("active");

    try {
      const res = await fetch(`/api/incident-analysis/${complaintId}`);
      if (!res.ok) throw new Error("Failed to fetch analysis");
      this.currentAnalysis = await res.json();
      this.renderDecisionSupport(this.currentAnalysis);

      // Render Graph & Map
      if (window.muleGraph) window.muleGraph.render(this.currentAnalysis.network_graph);
      
      const ds = this.currentAnalysis.decision_support;
      
      if (window.gisMap) {
        if (ds.trajectory) {
          window.gisMap.renderFullTrajectory(ds.trajectory);
        } else {
          const corridor = ds.taxonomy.predicted.primary_corridor;
          const topTp = ds.taxonomy.predicted.top_candidate_touchpoint;
          if (corridor) {
            const coords = corridor.center || (topTp ? topTp.coordinates : [28.1130, 77.0150]);
            const radius = corridor.radius_km || 15;
            window.gisMap.renderCorridor(coords, radius, corridor.name, corridor.confidence);
            window.gisMap.renderTouchpoints(ds.candidate_touchpoints || []);
            if (topTp && topTp.coordinates) {
              const unit = topTp.police_jurisdiction ? `PCR Unit (${topTp.police_jurisdiction.split(' ')[0]})` : "Tactical PCR Unit";
              window.gisMap.animatePatrolCar(topTp.coordinates, unit);
            }
          }
        }
      }
    } catch (e) {
      console.error("Error selecting incident", e);
    }
  }

  renderDecisionSupport(analysis) {
    const inc = analysis.incident;
    const ds = analysis.decision_support;
    const tax = ds.taxonomy;

    // Case Header
    document.getElementById("val-incident-id").textContent = inc.complaint_id;
    document.getElementById("val-priority-badge").textContent = ds.priority_assessment.priority_tier;
    document.getElementById("val-priority-badge").className = `badge-priority ${ds.priority_assessment.priority_tier === 'HIGH PRIORITY' ? 'badge-high' : 'badge-medium'}`;

    // Observed Card
    document.getElementById("obs-amount").textContent = `INR ${inc.disputed_amount_inr.toLocaleString()}`;
    document.getElementById("obs-scam").textContent = inc.scam_category.replace(/_/g, ' ');
    document.getElementById("obs-origin").textContent = `${inc.origin_jurisdiction.district}, ${inc.origin_jurisdiction.state}`;
    document.getElementById("obs-utr").textContent = inc.primary_utr || 'N/A';

    // Derived Card
    document.getElementById("der-delay").textContent = `${tax.derived.reporting_delay_minutes} minutes`;
    document.getElementById("der-hops").textContent = `${tax.derived.total_mule_hops} multi-rail hops`;
    document.getElementById("der-velocity").textContent = `${tax.derived.average_hop_velocity_mins} mins / hop`;
    document.getElementById("der-transit").textContent = tax.derived.inter_state_transit ? 'YES (Inter-State Route)' : 'Intra-State';

    // Predicted Card
    const priCorridor = tax.predicted.primary_corridor;
    document.getElementById("pred-corridor").textContent = `${priCorridor.name} (${(priCorridor.confidence * 100).toFixed(1)}%)`;
    
    const altText = tax.predicted.alternative_corridors.map(a => `${a.name.split(' ')[0]} (${(a.confidence * 100).toFixed(0)}%)`).join(', ');
    document.getElementById("pred-alternatives").textContent = altText || 'None';
    document.getElementById("pred-patrol-eta").textContent = tax.predicted.estimated_patrol_eta;
    document.getElementById("pred-window").textContent = `~${tax.predicted.remaining_withdrawal_window_mins} mins`;

    // Recommended
    document.getElementById("rec-action-summary").textContent = tax.recommended.action_summary;

    // Ranked Touchpoints
    const tpList = document.getElementById("ranked-touchpoints-list");
    tpList.innerHTML = "";
    (ds.candidate_touchpoints || []).forEach((tp, idx) => {
      const item = document.createElement("div");
      item.className = "touchpoint-rank-item";
      item.innerHTML = `
        <div class="tp-top">
          <span class="tp-name">#${idx + 1} ${tp.institution_name}</span>
          <span class="tp-score">${(tp.ranking_score * 100).toFixed(0)}% Score</span>
        </div>
        <div style="font-size: 10.5px; color: var(--text-muted);">${tp.location_name} • ${tp.touchpoint_type.replace(/_/g, ' ')}</div>
        <div class="factor-tags">
          ${tp.contributing_factors.map(f => `<span class="factor-tag">${f}</span>`).join('')}
        </div>
      `;
      tpList.appendChild(item);
    });

    // ── Review Report (auto-generated for investigator) ──────────────────────
    this.renderReviewReport(inc, ds, analysis);
  }

  renderReviewReport(inc, ds, analysis) {
    const rrSection = document.getElementById('review-report-section');
    if (!rrSection) return;
    rrSection.style.display = 'block';

    // Validation card
    const val = inc._validation || {};
    const isValid = val.is_valid !== false;
    const valScore = val.validation_score || 80;
    const rrValCard = document.getElementById('rr-validation-card');
    if (rrValCard) {
      rrValCard.style.background = isValid ? 'rgba(0,255,136,0.06)' : 'rgba(255,165,0,0.06)';
      rrValCard.style.borderColor = isValid ? 'rgba(0,255,136,0.2)' : 'rgba(255,165,0,0.3)';
      rrValCard.querySelector('div').style.color = isValid ? 'var(--emerald)' : 'var(--amber)';
      rrValCard.querySelector('div').textContent = isValid ? '✅ Transaction Verified & Fraud Confirmed' : '⚠️ Validation Warnings Present';
    }
    const rrValSummary = document.getElementById('rr-validation-summary');
    if (rrValSummary) rrValSummary.textContent = val.validation_summary || (isValid ? 'Complaint validated successfully.' : 'Validation warnings detected.');
    const rrValMeta = document.getElementById('rr-validation-meta');
    if (rrValMeta) {
      rrValMeta.innerHTML = `
        <span style="font-size:10px;background:rgba(0,229,255,0.1);color:var(--cyan);padding:2px 8px;border-radius:8px;font-weight:700;">Score: ${valScore}/100</span>
        <span style="font-size:10px;background:${isValid ? 'rgba(0,255,136,0.1)' : 'rgba(255,165,0,0.1)'};color:${isValid ? 'var(--emerald)' : 'var(--amber)'};padding:2px 8px;border-radius:8px;">Stage 1: ${(val.stage1_transaction_verified !== false) ? '✅ TX Verified' : '❌ TX Failed'}</span>
        <span style="font-size:10px;background:${isValid ? 'rgba(0,255,136,0.1)' : 'rgba(255,165,0,0.1)'};color:${isValid ? 'var(--emerald)' : 'var(--amber)'};padding:2px 8px;border-radius:8px;">Stage 2: ${(val.stage2_fraud_verified !== false) ? '✅ Fraud Confirmed' : '⚠️ Needs Review'}</span>
        <span style="font-size:10px;background:rgba(0,229,255,0.08);color:var(--text-secondary);padding:2px 8px;border-radius:8px;">Priority: ${ds.priority_score || 55}/100</span>
      `;
    }

    // Corridor prediction
    const priCorridor = ds.taxonomy.predicted.primary_corridor;
    const altCorridors = ds.taxonomy.predicted.alternative_corridors || [];
    const rrCorridor = document.getElementById('rr-corridor');
    if (rrCorridor) rrCorridor.textContent = `${priCorridor.name}  (${(priCorridor.confidence * 100).toFixed(1)}% confidence)`;
    const rrCorridorState = document.getElementById('rr-corridor-state');
    if (rrCorridorState) rrCorridorState.textContent = `📍 ${priCorridor.state} • Radius: ${priCorridor.radius_km || 12} km`;
    const rrCorridorAlts = document.getElementById('rr-corridor-alts');
    if (rrCorridorAlts) rrCorridorAlts.textContent = altCorridors.length
      ? `Alternatives: ${altCorridors.map(a => `${a.name} (${(a.confidence*100).toFixed(0)}%)`).join(' | ')}`
      : 'No significant alternative corridors';

    // Ranked ATMs
    const rrAtmList = document.getElementById('rr-atm-list');
    if (rrAtmList) {
      rrAtmList.innerHTML = '';
      (ds.candidate_touchpoints || []).slice(0, 5).forEach((tp, idx) => {
        const rankColors = ['var(--coral)', 'var(--amber)', 'var(--cyan)', 'var(--text-secondary)', 'var(--text-muted)'];
        const bar = Math.round((tp.ranking_score || 0.7) * 100);
        const div = document.createElement('div');
        div.style.cssText = 'background:rgba(255,255,255,0.03);border:1px solid var(--border-subtle);border-radius:6px;padding:8px 10px;';
        div.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span style="font-size:11.5px;font-weight:700;color:${rankColors[idx]};">#${idx+1} ${tp.institution_name}</span>
            <span style="font-family:var(--font-mono);font-size:11px;color:var(--cyan);font-weight:700;">${bar}%</span>
          </div>
          <div style="background:rgba(0,229,255,0.08);border-radius:4px;height:4px;margin-bottom:5px;">
            <div style="background:${rankColors[idx]};width:${bar}%;height:4px;border-radius:4px;transition:width 0.8s ease;"></div>
          </div>
          <div style="font-size:10px;color:var(--text-muted);">${tp.location_name || tp.district} • ${tp.touchpoint_type.replace(/_/g,' ')} ${tp.cctv_available ? '• 📹 CCTV' : ''}</div>
        `;
        rrAtmList.appendChild(div);
      });
    }

    // Recommended action
    const rrActionText = document.getElementById('rr-action-text');
    if (rrActionText) rrActionText.textContent = ds.taxonomy.recommended.action_summary;
  }

  async loadHeatmap() {
    const state = document.getElementById("filter-state").value;
    const typology = document.getElementById("filter-typology").value;
    const tpType = document.getElementById("filter-touchpoint").value;

    try {
      const res = await fetch(`/api/heatmap?state=${state}&typology=${typology}&touchpoint_type=${tpType}`);
      const data = await res.json();
      if (window.gisMap && data.predicted_corridors && data.predicted_corridors.length > 0) {
        // Render background corridors
      }
    } catch (e) {
      console.error("Failed to load heatmap", e);
    }
  }

  applyFilters() {
    this.loadHeatmap();
    const state = document.getElementById("filter-state").value;
    const typology = document.getElementById("filter-typology").value;
    const searchVal = (document.getElementById("input-search")?.value || "").trim().toLowerCase();

    let filtered = this.incidents;
    if (state !== "ALL") {
      filtered = filtered.filter(i =>
        i.origin_jurisdiction && i.origin_jurisdiction.state.toLowerCase() === state.toLowerCase()
      );
    }
    if (typology !== "ALL") {
      filtered = filtered.filter(i => i.scam_category === typology);
    }
    if (searchVal) {
      filtered = filtered.filter(i => {
        const idMatch = i.complaint_id && i.complaint_id.toLowerCase().includes(searchVal);
        const utrMatch = i.primary_utr && i.primary_utr.toLowerCase().includes(searchVal);
        const scamMatch = i.scam_category && i.scam_category.toLowerCase().includes(searchVal);
        const stateMatch = i.origin_jurisdiction && i.origin_jurisdiction.state.toLowerCase().includes(searchVal);
        const districtMatch = i.origin_jurisdiction && i.origin_jurisdiction.district.toLowerCase().includes(searchVal);
        return idMatch || utrMatch || scamMatch || stateMatch || districtMatch;
      });
    }
    this.renderIncidentList(filtered);
  }

  async approveTacticalAlert() {
    if (!this.currentIncidentId) {
      this.showToast("⚠️ Please select a complaint first.", "amber");
      return;
    }
    const btn = document.getElementById('btn-approve-alert');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Dispatching Alerts...';

    try {
      // Use the new /api/review-complaint endpoint for proper workflow
      const res = await fetch("/api/review-complaint", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Role": this.currentRole },
        body: JSON.stringify({
          complaint_id: this.currentIncidentId,
          decision: "APPROVE",
          reviewer_id: "OFFICER_KA_8841",
          reviewer_role: this.currentRole
        })
      });
      const data = await res.json();

      if (data.status === 'APPROVED_AND_ALERTS_DISPATCHED') {
        const alertCount = data.alerts?.length || 4;
        this.showToast(
          `✅ Approved! ${alertCount} alerts dispatched → LEA (Samanvay), Banks (CFCFRMS), SMS & Email. Victim timeline updated.`,
          "emerald"
        );
        // Update the incident card's workflow stage
        const inc = this.incidents.find(i => i.complaint_id === this.currentIncidentId);
        if (inc) { inc._workflowStage = 'ALERTS_DISPATCHED'; this.renderIncidentList(this.incidents); }

        // Show alert details in a summary
        if (data.alerts) {
          const alertSummary = data.alerts.map(a => `• ${a.channel}: ${a.target}`).join('\n');
          setTimeout(() => alert(`Alerts Dispatched to:\n\n${alertSummary}`), 100);
        }
      } else {
        // Fallback to old alerts endpoint
        await fetch("/api/alerts/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            incident_id: this.currentIncidentId,
            priority_tier: "HIGH PRIORITY",
            target_jurisdiction: "Nuh District Cyber Crime PS / Tauru Beat",
            target_corridor: "Mewat-Nuh Rural Corridor",
            channels: ["DASHBOARD", "WEBHOOK", "SMS_SIMULATED"],
            alert_message: `TACTICAL ALERT: High-probability cash-out for incident #${this.currentIncidentId}`
          })
        });
        this.showToast(`🛡️ Tactical Alert Dispatched`, "emerald");
      }
    } catch (e) {
      this.showToast("❌ Failed to dispatch alerts: " + e.message, "coral");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }

  async prepareRequisitions() {
    if (!this.currentIncidentId) return;
    try {
      const res = await fetch("/api/prepare-requisition", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Role": this.currentRole },
        body: JSON.stringify({
          complaint_id: this.currentIncidentId,
          officer_id: "OFFICER_KA_8841"
        })
      });
      const data = await res.json();
      alert(
        `REQUISITION PACKAGE GENERATED:\n\n` +
        `1. ${data.cfcfrms_freeze_package.document_type}\n` +
        `   ID: ${data.cfcfrms_freeze_package.requisition_id}\n` +
        `   Target Accounts: ${data.cfcfrms_freeze_package.targeted_beneficiary_accounts.length} beneficiary nodes flagged\n\n` +
        `2. ${data.section_94_bnss_notice.statutory_heading}\n` +
        `   ID: ${data.section_94_bnss_notice.notice_id}\n` +
        `   Demand: 3-hour CCTV preservation & electronic journal dump\n\n` +
        `3. ${data.samanvay_transfer_slip.document_type}\n` +
        `   Inter-State: ${data.samanvay_transfer_slip.originating_state} -> ${data.samanvay_transfer_slip.destination_state}`
      );
      this.showToast("📄 Requisitions Prepared & Logged to Tamper-Evident Audit Trail", "cyan");
    } catch (e) {
      this.showToast("Error preparing requisitions", "coral");
    }
  }

  downloadDossierPdf() {
    if (!this.currentIncidentId) return;
    window.location.href = `/api/dossier/${this.currentIncidentId}`;
    this.showToast("📥 Generating & Downloading Forensic Integrity Report (PDF)...", "cyan");
  }

  async overrideLead() {
    if (!this.currentIncidentId) {
      this.showToast("⚠️ Please select a complaint first.", "amber");
      return;
    }
    const reason = prompt("Enter rejection reason (will be logged to audit trail and trigger re-validation):\ne.g. 'UTR not found in banking records', 'Amount inconsistency', 'Duplicate complaint'");
    if (!reason || !reason.trim()) return;

    const btn = document.getElementById('btn-override');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span>🔄</span> Sending for Re-validation...';

    try {
      const res = await fetch("/api/review-complaint", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Role": this.currentRole },
        body: JSON.stringify({
          complaint_id: this.currentIncidentId,
          decision: "REJECT",
          rejection_reason: reason.trim(),
          reviewer_id: "OFFICER_KA_8841",
          reviewer_role: this.currentRole
        })
      });
      const data = await res.json();

      if (data.status === 'PERMANENTLY_REJECTED') {
        this.showToast(`❌ Complaint permanently rejected after ${data.retry_count || 3} attempts. Victim notified.`, "coral");
        const inc = this.incidents.find(i => i.complaint_id === this.currentIncidentId);
        if (inc) { inc._workflowStage = 'PERMANENTLY_REJECTED'; this.renderIncidentList(this.incidents); }
      } else {
        const retryCount = data.retry_count || 1;
        const passed = data.re_validation?.is_valid;
        const newStage = data.new_stage;
        if (passed) {
          this.showToast(
            `🔄 Re-validation passed (attempt ${retryCount}/3). Complaint back in review queue. New stage: ${newStage}.`,
            "amber"
          );
        } else {
          this.showToast(
            `⚠️ Re-validation raised issues (attempt ${retryCount}/3). Revision requested from victim. Stage: ${newStage}.`,
            "amber"
          );
        }
        const inc = this.incidents.find(i => i.complaint_id === this.currentIncidentId);
        if (inc) { inc._workflowStage = newStage; this.renderIncidentList(this.incidents); }
      }
    } catch (e) {
      this.showToast("❌ Failed to process rejection: " + e.message, "coral");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }

  openIntakeModal() {
    const modal = document.getElementById("modal-intake-backdrop");
    if (modal) modal.style.display = "flex";
  }

  closeIntakeModal() {
    const modal = document.getElementById("modal-intake-backdrop");
    if (modal) modal.style.display = "none";
  }

  applyScenarioPreset(presetKey) {
    const presets = {
      cbi_digital_arrest: {
        scam: "DIGITAL_ARREST",
        amt: 1250000,
        state: "Maharashtra",
        district: "Mumbai Suburban",
        delay: 20,
        corridor: "mewat_nuh_rural",
        utr: "428938102914"
      },
      jamtara_electricity: {
        scam: "ELECTRICITY_KYC_APK_FRAUD",
        amt: 95000,
        state: "West Bengal",
        district: "Kolkata",
        delay: 35,
        corridor: "jamtara_cyber_hub",
        utr: "429184719203"
      },
      investment_stock: {
        scam: "INVESTMENT_STOCK_SCAM",
        amt: 2800000,
        state: "Karnataka",
        district: "Bengaluru Urban",
        delay: 15,
        corridor: "delhi_rohini_urban",
        utr: "429583719402"
      },
      loan_app: {
        scam: "LOAN_APP_EXTORTION",
        amt: 320000,
        state: "Maharashtra",
        district: "Pune",
        delay: 40,
        corridor: "surat_trade_hub",
        utr: "429819203914"
      }
    };

    const p = presets[presetKey];
    if (!p) return;

    document.getElementById("modal-scam-category").value = p.scam;
    document.getElementById("modal-amount").value = p.amt;
    document.getElementById("modal-origin-state").value = p.state;
    document.getElementById("modal-origin-district").value = p.district;
    
    const slider = document.getElementById("modal-delay-slider");
    if (slider) {
      slider.value = p.delay;
      slider.dispatchEvent(new Event("input"));
    }
    
    document.getElementById("modal-target-corridor").value = p.corridor;
    document.getElementById("modal-utr").value = p.utr;

    // Reset hops to auto for presets
    const hopsSelect = document.getElementById("modal-num-hops");
    const hopsDisplay = document.getElementById("hops-display");
    if (hopsSelect) { hopsSelect.value = ""; }
    if (hopsDisplay) { hopsDisplay.textContent = "Auto"; }

    // Highlight matching scam tile
    document.querySelectorAll(".scam-tile").forEach(t => {
      t.classList.toggle("active", t.getAttribute("data-scam") === p.scam);
    });

    // Highlight matching time pill if exists
    document.querySelectorAll(".time-pill-btn").forEach(b => {
      b.classList.toggle("active", parseInt(b.getAttribute("data-mins")) === p.delay);
    });

    // Highlight matching quick amount button
    document.querySelectorAll(".btn-quick-amt").forEach(b => {
      b.classList.toggle("active", parseFloat(b.getAttribute("data-val")) === p.amt);
    });

    this.showToast(`Loaded Preset: ${presetKey.replace(/_/g, ' ').toUpperCase()}`, "cyan");
  }

  async submitCustomIncidentAndTrack() {
    const btnSubmit = document.getElementById("btn-modal-submit");
    const scamCategory = document.getElementById("modal-scam-category").value;
    const amount = parseFloat(document.getElementById("modal-amount").value);
    const originState = document.getElementById("modal-origin-state").value;
    const originDistrict = document.getElementById("modal-origin-district").value.trim();
    const delayMins = parseInt(document.getElementById("modal-delay-slider").value) || 25;
    const utr = document.getElementById("modal-utr").value.trim() || ("4289" + Math.floor(10000000 + Math.random() * 90000000));
    const corridorHint = document.getElementById("modal-target-corridor")?.value;
    const hopsRaw = document.getElementById("modal-num-hops")?.value;
    const numMuleHops = hopsRaw ? parseInt(hopsRaw) : null;

    // Additional dynamic fields
    const victimName = document.getElementById("modal-victim-name")?.value.trim() || null;
    const victimPhone = document.getElementById("modal-victim-phone")?.value.trim() || null;
    const suspectBankHint = document.getElementById("modal-suspect-bank")?.value || null;
    const touchpointModality = document.getElementById("modal-touchpoint-pref")?.value || null;

    // Destination choice: Auto-trace vs Custom suspect destination
    const isCustomDest = document.getElementById("dest-choice-custom")?.checked;
    let destState = null;
    let destDistrict = null;
    if (isCustomDest) {
      destState = document.getElementById("modal-dest-state")?.value || null;
      destDistrict = document.getElementById("modal-dest-district")?.value.trim() || null;
      if (!destDistrict && destState) {
        destDistrict = this.districtSuggestions[destState] || `${destState} Center`;
      }
    }

    // --- Client-side validation ---
    if (!amount || amount <= 0) {
      this.showToast("⚠️ Please enter a valid Disputed Amount (INR > 0)", "coral");
      document.getElementById("modal-amount").focus();
      return;
    }
    if (!originState) {
      this.showToast("⚠️ Please select an Origin State", "coral");
      return;
    }

    // Auto-fill district if blank
    const effectiveDistrict = originDistrict ||
      this.districtSuggestions[originState] ||
      `${originState} District`;

    // --- Animated progress feedback ---
    const originalText = btnSubmit.innerHTML;
    const steps = [
      `<span>🔍</span> Validating Incident Parameters...`,
      `<span>🧠</span> Running Stage-1 Corridor Classifier...`,
      `<span>📍</span> Synthesizing & Ranking Touchpoints...`,
      `<span>🗺️</span> Tracking Inter-State Money Trail...`,
    ];
    let stepIdx = 0;
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = steps[0];
    const stepTimer = setInterval(() => {
      stepIdx = Math.min(stepIdx + 1, steps.length - 1);
      btnSubmit.innerHTML = steps[stepIdx];
    }, 600);

    try {
      const res = await fetch("/api/simulate-incident", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scam_category: scamCategory,
          disputed_amount_inr: amount,
          origin_state: originState,
          origin_district: effectiveDistrict,
          destination_state: destState,
          destination_district: destDistrict,
          preferred_touchpoint_modality: touchpointModality,
          suspect_bank_hint: suspectBankHint,
          victim_name: victimName,
          victim_phone: victimPhone,
          reporting_delay_minutes: delayMins,
          primary_utr: utr,
          target_corridor_hint: (corridorHint && corridorHint !== "AUTO") ? corridorHint : null,
          num_mule_hops: numMuleHops
        })
      });

      if (!res.ok) {
        let errMsg = `Server error (${res.status})`;
        try {
          const errBody = await res.json();
          if (errBody.detail) errMsg = typeof errBody.detail === "string"
            ? errBody.detail
            : JSON.stringify(errBody.detail);
        } catch (_) {}
        throw new Error(errMsg);
      }

      const data = await res.json();
      const incident = data.incident;
      const ds = data.decision_support;

      // Close modal
      this.closeIntakeModal();

      // Put new incident at top of queue
      this.incidents = this.incidents.filter(i => i.complaint_id !== incident.complaint_id);
      this.incidents.unshift(incident);
      this.renderIncidentList(this.incidents);

      // Switch view to GIS Map
      this.switchCanvasView("map");

      // Select and render analysis
      await this.selectIncident(incident.complaint_id);

      // Explicitly track full trajectory on GIS Map if present
      if (window.gisMap) {
        if (ds.trajectory) {
          window.gisMap.renderFullTrajectory(ds.trajectory);
        } else {
          const priCorridor = ds.taxonomy.predicted.primary_corridor;
          const topTp = ds.taxonomy.predicted.top_candidate_touchpoint;
          if (priCorridor) {
            const coords = priCorridor.center || (topTp ? topTp.coordinates : [28.1130, 77.0150]);
            const radiusKm = priCorridor.radius_km || 15;
            window.gisMap.renderCorridor(coords, radiusKm, priCorridor.name, priCorridor.confidence);
            window.gisMap.renderTouchpoints(ds.candidate_touchpoints || []);

            if (topTp && topTp.coordinates) {
              const unit = topTp.police_jurisdiction ? `PCR Unit (${topTp.police_jurisdiction.split(' ')[0]})` : "PCR Tactical Unit";
              window.gisMap.animatePatrolCar(topTp.coordinates, unit);
            }
          }
        }
      }

      const priCorridor = ds.taxonomy.predicted.primary_corridor;
      const eta = ds.taxonomy.predicted.estimated_patrol_eta || "8-12 mins";
      const win = ds.taxonomy.predicted.remaining_withdrawal_window_mins || "25 mins";
      const destName = isCustomDest && destDistrict ? `${destDistrict}, ${destState}` : priCorridor.name;
      this.showToast(`🎯 Live Trail Tracked: ${effectiveDistrict} ➔ ${destName} | Unit ETA: ${eta} | Window: ~${win}m`, "cyan");

    } catch (e) {
      console.error("Error during custom intake:", e);
      this.showToast(`❌ ${e.message || "Failed to process incident intake"}`, "coral");
    } finally {
      clearInterval(stepTimer);
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = originalText;
    }
  }

  showToast(msg, type = "cyan") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.style.borderLeftColor = type === "coral" ? "var(--coral)" : type === "emerald" ? "var(--emerald)" : type === "amber" ? "var(--amber)" : "var(--cyan)";
    toast.innerHTML = `<span style="font-size: 14px;">⚡</span> <span>${msg}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  initWebSocket() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws/live-stream`;
    
    try {
      this.socket = new WebSocket(wsUrl);
      this.socket.onopen = () => {
        document.getElementById("status-live-text").textContent = "LIVE REAL-TIME FEED";
      };
      this.socket.onmessage = (evt) => {
        const msg = JSON.parse(evt.data);
        if (msg.type === "NEW_INCIDENT") {
          this.showToast(`🚨 Live 1930 Feed: Incident #${msg.complaint_id} (${msg.scam_category})`, "coral");
          this.loadIncidents();
        }
      };
      this.socket.onclose = () => {
        document.getElementById("status-live-text").textContent = "REST FALLBACK MODE";
      };
    } catch (e) {
      document.getElementById("status-live-text").textContent = "REST FALLBACK MODE";
    }
  }
}

window.dashboardApp = new DashboardApp();
window.addEventListener("DOMContentLoaded", () => window.dashboardApp.init());
