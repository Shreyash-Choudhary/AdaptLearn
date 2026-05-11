/**
 * script.js  –  AdaptLearn interactive behaviour
 * Handles: upload page, quiz page, result page
 */

document.addEventListener("DOMContentLoaded", () => {

  // ── Detect which page we're on ─────────────────────────────
  const page = document.body.classList.contains("upload-page") ? "upload"
             : document.body.classList.contains("quiz-page")   ? "quiz"
             : document.body.classList.contains("result-page") ? "result"
             : null;

  if (page === "upload") initUploadPage();
  if (page === "quiz")   initQuizPage();
  if (page === "result") initResultPage();
});


/* =============================================================
   UPLOAD PAGE
   ============================================================= */
function initUploadPage() {
  const dropZone   = document.getElementById("dropZone");
  const fileInput  = document.getElementById("pdf_file");
  const filePreview= document.getElementById("filePreview");
  const fileName   = document.getElementById("fileName");
  const clearBtn   = document.getElementById("clearFile");
  const submitBtn  = document.getElementById("submitBtn");
  const uploadForm = document.getElementById("uploadForm");
  const loadingOverlay = document.getElementById("loadingOverlay");

  // ── Drag & drop ──────────────────────────────────────────
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFileSelection(files[0]);
  });

  // ── Native file picker ────────────────────────────────────
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) handleFileSelection(fileInput.files[0]);
  });

  // ── Clear selected file ───────────────────────────────────
  clearBtn.addEventListener("click", () => {
    fileInput.value = "";
    filePreview.classList.add("hidden");
    submitBtn.disabled = true;
  });

  // ── Form submit – show loading overlay ────────────────────
  uploadForm.addEventListener("submit", (e) => {
    if (!fileInput.files.length) { e.preventDefault(); return; }
    showLoadingOverlay();
  });

  /** Display file name and enable the submit button */
  function handleFileSelection(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please select a valid PDF file.");
      return;
    }
    // Transfer file to the real input (needed for drag-drop)
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;

    fileName.textContent = file.name;
    filePreview.classList.remove("hidden");
    submitBtn.disabled = false;
  }

  /** Show the loading overlay and animate steps */
  function showLoadingOverlay() {
    loadingOverlay.classList.remove("hidden");

    const steps = [
      document.getElementById("lstep1"),
      document.getElementById("lstep2"),
      document.getElementById("lstep3"),
    ];
    // Animate each step in sequence (visual only – actual timing is Flask's)
    let i = 0;
    const interval = setInterval(() => {
      if (i > 0) steps[i - 1].classList.replace("active", "done");
      if (i < steps.length) {
        steps[i].classList.add("active");
        i++;
      } else {
        clearInterval(interval);
      }
    }, 4000);   // 4 s per step
  }
}


/* =============================================================
   QUIZ PAGE
   ============================================================= */
function initQuizPage() {
  const radios       = document.querySelectorAll(".option-radio");
  const submitBtn    = document.getElementById("submitBtn");
  const submitHint   = document.getElementById("submitHint");
  const progressFill = document.getElementById("progressFill");
  const answeredSpan = document.getElementById("answeredCount");
  const summaryToggle= document.getElementById("summaryToggle");
  const summaryBody  = document.getElementById("summaryBody");
  const toggleArrow  = document.getElementById("toggleArrow");

  // Detect total questions from radio groups
  const questionSet = new Set();
  radios.forEach(r => questionSet.add(r.dataset.q));
  const totalQuestions = questionSet.size;

  const answered = new Set();   // tracks which questions have been answered

  // ── Summary panel toggle ──────────────────────────────────
  summaryToggle.addEventListener("click", () => {
    summaryBody.classList.toggle("hidden");
    toggleArrow.classList.toggle("open");
  });

  // ── Radio change → update progress ───────────────────────
  radios.forEach((radio) => {
    radio.addEventListener("change", () => {
      const qIndex = radio.dataset.q;
      answered.add(qIndex);

      // Highlight the card
      document.getElementById(`qcard-${qIndex}`).classList.add("answered");

      // Update progress bar
      const pct = (answered.size / totalQuestions) * 100;
      progressFill.style.width = pct + "%";
      answeredSpan.textContent = answered.size;

      // Enable submit only when all answered
      if (answered.size === totalQuestions) {
        submitBtn.disabled = false;
        submitHint.textContent = "All questions answered. Ready to submit!";
      }
    });
  });
}


/* =============================================================
   RESULT PAGE
   ============================================================= */
function initResultPage() {
  // SCORE_PERCENT is injected inline by result.html
  const pct = typeof SCORE_PERCENT !== "undefined" ? SCORE_PERCENT : 0;

  animateScoreRing(pct);
  animateScoreText(pct);
}

/**
 * Animate the SVG ring from 0 → pct.
 * The circle circumference is 2π × r = 2π × 52 ≈ 326.73
 */
function animateScoreRing(pct) {
  const CIRCUMFERENCE = 326.73;
  const ringFill  = document.getElementById("ringFill");
  if (!ringFill) return;

  const offset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;

  // Trigger animation after a short delay so the CSS transition fires
  requestAnimationFrame(() => {
    setTimeout(() => {
      ringFill.style.strokeDashoffset = offset;
    }, 150);
  });

  // Colour feedback
  if (pct >= 80) ringFill.style.stroke = "#22c55e";        // green
  else if (pct >= 60) ringFill.style.stroke = "#f5a623";   // amber
  else if (pct >= 40) ringFill.style.stroke = "#f59e0b";   // orange
  else ringFill.style.stroke = "#ef4444";                  // red
}

/** Count up the score percentage text from 0 → pct */
function animateScoreText(pct) {
  const el = document.getElementById("scorePercent");
  if (!el) return;

  let current = 0;
  const duration = 1200;  // ms
  const step     = pct / (duration / 16);  // ~60fps

  const timer = setInterval(() => {
    current = Math.min(current + step, pct);
    el.textContent = Math.round(current) + "%";
    if (current >= pct) clearInterval(timer);
  }, 16);
}
