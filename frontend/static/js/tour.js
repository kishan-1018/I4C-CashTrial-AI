/**
 * 1-Click Interactive Guided Case Tour Mode
 * Walks evaluators through the complete end-to-end pan-India tri-state workflow
 * in 5 visual, animated steps.
 */

class CaseTourController {
  constructor() {
    this.currentStep = 0;
    this.tourData = null;
    this.stepperEl = null;
    this.stepTextEl = null;
    this.dots = [];
    this.isAutoPlaying = false;
    this.timer = null;
  }

  init() {
    this.stepperEl = document.getElementById("tour-stepper");
    this.stepTextEl = document.getElementById("tour-step-text");
    this.dots = document.querySelectorAll(".tour-step-dot");
  }

  async startTour() {
    if (!this.stepperEl) this.init();
    this.stepperEl.style.display = "flex";
    
    // Fetch Demo Scenario 1 (Bengaluru -> Nuh Tri-State Case)
    try {
      const res = await fetch("/api/demo-scenarios");
      const scenarios = await res.json();
      this.tourData = scenarios[0];
    } catch (e) {
      console.error("Failed to load tour data", e);
      return;
    }

    this.currentStep = 1;
    this.executeStep(this.currentStep);
  }

  updateStepperUI(stepNum, narrative) {
    this.stepTextEl.innerHTML = `<b>Step ${stepNum}/5:</b> ${narrative}`;
    this.dots.forEach((dot, idx) => {
      dot.classList.remove("active", "completed");
      if (idx + 1 === stepNum) dot.classList.add("active");
      else if (idx + 1 < stepNum) dot.classList.add("completed");
    });
  }

  async executeStep(stepNum) {
    switch (stepNum) {
      case 1:
        // Step 1: Ingestion
        this.updateStepperUI(1, "1930 NCRP Complaint Ingested (Bengaluru, Karnataka — INR 350,000 Lost)");
        window.dashboardApp.selectIncident(this.tourData.complaint_id);
        window.dashboardApp.showToast("⚡ [Step 1] Ingested Live Incident #NCRP-DEMO-2026-01 from 1930 Portal", "cyan");
        break;

      case 2:
        // Step 2: Response Priority Triage
        this.updateStepperUI(2, "AI Priority Triage: Reporting delay is 28m (<45m window) → Classified as HIGH PRIORITY");
        window.dashboardApp.showToast("🚨 [Step 2] AI Response Urgency: HIGH PRIORITY (Opportunity Window Active)", "coral");
        // Scroll right panel to top
        document.getElementById("panel-decision").scrollTop = 0;
        break;

      case 3:
        // Step 3: Graph Tracing
        this.updateStepperUI(3, "Multi-Rail Graph Engine: Tracing money trail (Kolkata Wallet → Assam Bank → Nuh Terminal Account)");
        window.dashboardApp.switchCanvasView("graph");
        window.dashboardApp.showToast("🔗 [Step 3] Extracted 3-Hop Ego Network & Velocity Trails", "violet");
        break;

      case 4:
        // Step 4: Spatio-Temporal Prediction & Ranking
        this.updateStepperUI(4, "Predictive Engine: Mewat-Nuh Corridor (79% Confidence) + Punhana CSP Ranked #1");
        window.dashboardApp.switchCanvasView("map");
        
        // Focus map to Mewat and start patrol animation
        if (window.gisMap) {
          window.gisMap.renderCorridor([28.1130, 77.0150], 15, "Mewat-Nuh Rural Corridor", 0.79);
          window.gisMap.animatePatrolCar([28.1130, 77.0150], "PCR Unit P-12 (Tauru Circle)");
        }
        window.dashboardApp.showToast("🔮 [Step 4] Corridor Hotspot Pinpointed: Tactical Patrol En-Route", "cyan");
        break;

      case 5:
        // Step 5: Action & Requisition Preparation
        this.updateStepperUI(5, "Decision Support: Dispatched Samanvay Alert + Generated CFCFRMS Freeze & Sec 94 BNSS Notice");
        window.dashboardApp.prepareRequisitions();
        window.dashboardApp.showToast("🛡️ [Step 5] Statutory Notices & Integrity Dossier Prepared for Review", "emerald");
        break;
    }
  }

  nextStep() {
    if (this.currentStep < 5) {
      this.currentStep++;
      this.executeStep(this.currentStep);
    } else {
      this.endTour();
    }
  }

  prevStep() {
    if (this.currentStep > 1) {
      this.currentStep--;
      this.executeStep(this.currentStep);
    }
  }

  endTour() {
    if (this.stepperEl) this.stepperEl.style.display = "none";
    window.dashboardApp.showToast("✅ Guided Simulation Completed Successfully", "emerald");
  }
}

window.caseTour = new CaseTourController();
