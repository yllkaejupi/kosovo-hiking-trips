const statusEl = document.getElementById("hikes-status");
const gridEl = document.getElementById("hikes-grid");
const difficultySelect = document.getElementById("filter-difficulty");
const statusButtons = document.querySelectorAll(".filter-btn");

let allHikes = [];                                   // every trip, never changed after loading
const filters = { difficulty: "all", status: "all" }; // what the user picked

// ---------- Helpers ----------

// Escapes <, >, & etc. so scraped text can't inject HTML (prevents XSS)
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

// "2027-06-25" -> "25 Jun 2027"
function formatDate(isoDate) {
  const date = new Date(isoDate + "T00:00:00");
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function getDateText(hike) {
  if (hike.date_status === "on_request") return "Dates on request";
  if (!hike.start_date) return "Date unknown";
  if (hike.end_date && hike.end_date !== hike.start_date) {
    return `${formatDate(hike.start_date)} – ${formatDate(hike.end_date)}`;
  }
  return formatDate(hike.start_date);
}

// Today's date as "YYYY-MM-DD" in the user's local time zone
function getTodayIso() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// A trip is upcoming if it hasn't ended yet, or has no date at all ("on request")
function isUpcoming(hike, today) {
  const lastDay = hike.end_date ?? hike.start_date;
  if (!lastDay) return true;
  return lastDay >= today;
}

// Map any difficulty text to one of 3 levels
function getDifficultyLevel(difficulty) {
  const d = difficulty.toLowerCase();

  // Via ferrata grades: "VF A" (easiest) ... "VF E" (hardest)
  const vf = d.match(/^vf\s*([a-e])/);
  if (vf) {
    const grade = vf[1];
    if (grade === "a") return "easy";
    if (grade === "b" || grade === "c") return "medium";
    return "hard";                       // d or e
  }

  if (["beginner", "easy"].includes(d)) return "easy";
  if (["intermediate", "moderate", "medium", "easy to moderate"].includes(d)) return "medium";
  if (["advanced", "hard", "difficult", "expert"].includes(d)) return "hard";
  return "other";                        // unknown -> neutral style
}

// ---------- Building the cards ----------

function createCard(hike) {
  // Only keep the details that exist for this trip
  const details = [
    hike.distance_km && `${hike.distance_km} km`,
    hike.elevation_gain_m && `↑ ${hike.elevation_gain_m} m`,
    hike.duration_days && `${hike.duration_days} day${hike.duration_days > 1 ? "s" : ""}`,
    hike.duration_hours && `${hike.duration_hours} hour${hike.duration_hours > 1 ? "s" : ""}`,
    hike.price_eur && `from €${hike.price_eur}`,
  ].filter(Boolean);

  // "Advanced" -> "badge-hard", "VF B" -> "badge-medium"
  const difficultyClass = hike.difficulty
    ? "badge-" + getDifficultyLevel(hike.difficulty)
    : "";

  const badge = hike.difficulty
    ? `<span class="badge ${difficultyClass}">${escapeHtml(hike.difficulty)}</span>`
    : "";

  const url = hike.url?.startsWith("http") ? hike.url : "#";

  return `
    <article class="hike-card">
      <p class="hike-date">${escapeHtml(getDateText(hike))}</p>
      <h2 class="hike-title">${escapeHtml(hike.title)}</h2>
      ${hike.category || badge ? `
        <p class="hike-tags">
          ${escapeHtml(hike.category || "")}
          ${badge}
        </p>` : ""}
      <p class="hike-location">📍 ${escapeHtml(hike.location || "Location not listed")}</p>
      ${details.length ? `<p class="hike-details">${escapeHtml(details.join(" · "))}</p>` : ""}
      <a class="hike-link" href="${escapeHtml(url)}" target="_blank" rel="noopener">View trip →</a>
    </article>
  `;
}

function renderHikes(hikes) {
  gridEl.innerHTML = hikes.map(createCard).join("");
}

// ---------- Filters ----------

// Older/manual trips may not have date_status, so work it out
function getStatus(hike) {
  return hike.date_status ?? (hike.start_date ? "scheduled" : "unknown");
}

function fillDifficultyOptions(hikes) {
  const levelOrder = { easy: 0, medium: 1, hard: 2, other: 3 };
  const rank = (d) => levelOrder[getDifficultyLevel(d)];

  const difficulties = [...new Set(hikes.map((h) => h.difficulty).filter(Boolean))];
  difficulties.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));

  for (const difficulty of difficulties) {
    const option = document.createElement("option");
    option.value = difficulty;
    option.textContent = difficulty;
    difficultySelect.appendChild(option);
  }
}

function applyFilters() {
  const visible = allHikes.filter((hike) => {
    const matchesDifficulty =
      filters.difficulty === "all" || hike.difficulty === filters.difficulty;
    const matchesStatus =
      filters.status === "all" || getStatus(hike) === filters.status;
    return matchesDifficulty && matchesStatus;
  });

  renderHikes(visible);
  statusEl.textContent = visible.length
    ? `Showing ${visible.length} of ${allHikes.length} trips`
    : "No trips match these filters.";
}

difficultySelect.addEventListener("change", () => {
  filters.difficulty = difficultySelect.value;
  applyFilters();
});

statusButtons.forEach((button) => {
  button.addEventListener("click", () => {
    filters.status = button.dataset.status;
    statusButtons.forEach((b) => b.classList.toggle("active", b === button));
    applyFilters();
  });
});

// ---------- Loading ----------

async function loadHikes() {
  try {
    const response = await fetch("hikes.json");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const hikes = await response.json();
    const today = getTodayIso();
    allHikes = hikes.filter((hike) => isUpcoming(hike, today));
    fillDifficultyOptions(allHikes);
    applyFilters();
  } catch (error) {
    console.error("Could not load hikes:", error);
    statusEl.textContent = "Sorry, the trips could not be loaded.";
  }
}

loadHikes();