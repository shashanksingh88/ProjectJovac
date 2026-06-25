const statuses = ["New Lead", "Contacted", "Meeting Scheduled", "Proposal Sent", "Negotiation", "Closed"];

let leads = [];
let tasks = [];
let selectedLeadId = null;

const leadRows = document.querySelector("#leadRows");
const leadForm = document.querySelector("#leadForm");
const selectedLead = document.querySelector("#selectedLead");
const outreachMessage = document.querySelector("#outreachMessage");
const tasksEl = document.querySelector("#tasks");
const pipelineStages = document.querySelector("#pipelineStages");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "CRM request failed");
  }
  return response.json();
}

async function loadData() {
  [leads, tasks] = await Promise.all([api("/api/leads"), api("/api/tasks")]);
  if (!selectedLeadId && leads.length) selectedLeadId = leads[0].id;
  if (!leads.some((lead) => lead.id === selectedLeadId) && leads.length) selectedLeadId = leads[0].id;
  render();
}

function selectedLeadRecord() {
  return leads.find((lead) => lead.id === selectedLeadId) || leads[0];
}

function renderMetrics() {
  const contacted = leads.filter((lead) => lead.status !== "New Lead").length;
  const active = leads.filter((lead) => lead.status !== "Closed").length;
  const meetings = leads.filter((lead) => lead.status === "Meeting Scheduled").length;
  const conversion = leads.length ? Math.round((leads.filter((lead) => lead.status === "Closed").length / leads.length) * 100) : 0;
  document.querySelector("#metricContacted").textContent = contacted;
  document.querySelector("#metricActive").textContent = active;
  document.querySelector("#metricMeetings").textContent = meetings;
  document.querySelector("#metricConversion").textContent = `${conversion}%`;
}

function renderRows() {
  leadRows.innerHTML = leads.map((lead) => {
    const priority = lead.priority.toLowerCase();
    return `
      <tr data-id="${lead.id}">
        <td>
          <button class="link-button" data-select="${lead.id}">
            <span class="institution">
              <strong>${lead.name}</strong>
              <small>${lead.location} | ${lead.type} | ${Number(lead.strength).toLocaleString()} students</small>
            </span>
          </button>
        </td>
        <td>${lead.contact}<br><small>${lead.email}</small></td>
        <td>${lead.interest}<br><small>${lead.source}</small></td>
        <td>
          <select data-status="${lead.id}">
            ${statuses.map((status) => `<option ${status === lead.status ? "selected" : ""}>${status}</option>`).join("")}
          </select>
        </td>
        <td><span class="pill priority-${priority}">${lead.priority} ${lead.score}</span></td>
        <td>${lead.nextBestAction}</td>
      </tr>
    `;
  }).join("");
}

function renderSelected() {
  const lead = selectedLeadRecord();
  if (!lead) {
    selectedLead.innerHTML = '<div class="insight"><strong>No leads yet</strong><p>Add an institution to begin.</p></div>';
    outreachMessage.value = "";
    return;
  }

  document.querySelector("#ownerName").textContent = lead.owner;
  selectedLead.innerHTML = `
    <div class="insight">
      <strong>${lead.name}</strong>
      <p>${lead.location}</p>
    </div>
    <div class="insight">
      <strong>${lead.priority} Priority Lead | ${lead.score}/100</strong>
      <p>${lead.name} has ${Number(lead.strength).toLocaleString()} students and a ${lead.source.toLowerCase()} source, making it a strong candidate for ${lead.interest.toLowerCase()}.</p>
      <small>AI engine: ${lead.aiSource}</small>
    </div>
    <div class="insight">
      <strong>Next Best Action</strong>
      <p>${lead.nextBestAction}</p>
    </div>
    <div class="insight">
      <strong>Follow-up Suggestion</strong>
      <p>${lead.followUpSuggestion}</p>
    </div>
  `;
  outreachMessage.value = lead.outreachMessage;
}

function renderPipeline() {
  pipelineStages.innerHTML = statuses.map((status) => {
    const stageLeads = leads.filter((lead) => lead.status === status);
    return `
      <div class="stage">
        <strong>${status} (${stageLeads.length})</strong>
        ${stageLeads.length ? stageLeads.map((lead) => `<span>${lead.name}</span>`).join("") : "<span>No institutions</span>"}
      </div>
    `;
  }).join("");
}

function renderTasks() {
  tasksEl.innerHTML = tasks.length ? tasks.map((task) => `
    <div class="task">
      <div>
        <strong>${task.title}</strong>
        <small>${task.lead} | ${task.owner}</small>
      </div>
      <span class="pill">${task.due}</span>
    </div>
  `).join("") : '<div class="task"><div><strong>No follow-ups yet</strong><small>Create one from AI Intelligence.</small></div></div>';
}

function render() {
  renderMetrics();
  renderRows();
  renderSelected();
  renderPipeline();
  renderTasks();
}

document.querySelector("#addLead").addEventListener("click", () => {
  leadForm.classList.toggle("open");
});

leadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(leadForm);
  const payload = Object.fromEntries(formData.entries());
  payload.strength = Number(payload.strength);
  const lead = await api("/api/leads", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  selectedLeadId = lead.id;
  leadForm.reset();
  leadForm.classList.remove("open");
  await loadData();
});

leadRows.addEventListener("click", (event) => {
  const selectButton = event.target.closest("[data-select]");
  if (!selectButton) return;
  selectedLeadId = Number(selectButton.dataset.select);
  renderSelected();
});

leadRows.addEventListener("change", async (event) => {
  if (!event.target.matches("[data-status]")) return;
  const leadId = Number(event.target.dataset.status);
  selectedLeadId = leadId;
  await api(`/api/leads/${leadId}`, {
    method: "PATCH",
    body: JSON.stringify({ status: event.target.value })
  });
  await loadData();
});

document.querySelector("#advanceStatus").addEventListener("click", async () => {
  const lead = selectedLeadRecord();
  if (!lead) return;
  selectedLeadId = lead.id;
  await api(`/api/leads/${lead.id}/advance`, { method: "POST" });
  await loadData();
});

document.querySelector("#createFollowUp").addEventListener("click", async () => {
  const lead = selectedLeadRecord();
  if (!lead) return;
  await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      leadId: lead.id,
      title: `Follow up with ${lead.contact}`,
      due: "Tomorrow"
    })
  });
  await loadData();
});

document.querySelector("#seedReminder").addEventListener("click", async () => {
  const review = await api("/api/ai-review", { method: "POST" });
  leads = review.leads;
  tasks = review.tasks;
  if (leads.length) selectedLeadId = leads[0].id;
  render();
});

loadData().catch((error) => {
  selectedLead.innerHTML = `<div class="insight"><strong>Backend unavailable</strong><p>${error.message}. Start Flask with: python server.py</p></div>`;
});
