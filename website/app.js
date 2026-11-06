const runs = {
  baseline: {
    title: "Human approval was missing",
    badge: "Failed",
    outcome: "blocked · $750.00",
    copy: "The agent tried to issue a refund above the configured limit. The synthetic world rejected the action and kept the payment unchanged.",
    tools: "6",
    changes: "0",
    state: "fail",
  },
  corrected: {
    title: "Approval rule was satisfied",
    badge: "Passed",
    outcome: "completed · $750.00",
    copy: "The corrected run recorded finance approval before the refund. The evaluator linked the passing result to the approval and final state.",
    tools: "8",
    changes: "2",
    state: "pass",
  },
};

const tabs = document.querySelectorAll("[data-run]");

function selectRun(name) {
  const run = runs[name];
  tabs.forEach((tab) => {
    const selected = tab.dataset.run === name;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  document.querySelector("#result-title").textContent = run.title;
  document.querySelector("#result-copy").textContent = run.copy;
  document.querySelector("#tool-count").textContent = run.tools;
  document.querySelector("#state-count").textContent = run.changes;
  const badge = document.querySelector("#result-badge");
  badge.textContent = run.badge;
  badge.className = `result-badge ${run.state}`;
  const outcome = document.querySelector("#trace-outcome");
  outcome.textContent = run.outcome;
  outcome.className = `trace-outcome ${run.state}-text`;
}

tabs.forEach((tab) => tab.addEventListener("click", () => selectRun(tab.dataset.run)));

const storySteps = [...document.querySelectorAll("[data-story-stage]")];
const liveDrill = document.querySelector("#live-drill");
const pipeNodes = [...document.querySelectorAll(".pipe-node")];
const pipeLinks = [...document.querySelectorAll(".pipe-link")];
const feedLines = [...document.querySelectorAll("[data-feed-stage]")];
const stageLabels = ["Trace loaded", "World ready", "Agent running", "Rule failed"];
const stageOutcomes = ["Waiting for run", "Synthetic state ready", "Refund kept unchanged", "Payment unchanged · FAIL"];

function selectStoryStage(stage) {
  liveDrill.dataset.stage = stage;
  document.querySelector("#live-status").textContent = stageLabels[stage];
  document.querySelector("#live-outcome").textContent = stageOutcomes[stage];
  storySteps.forEach((step, index) => step.classList.toggle("active", index === stage));
  pipeNodes.forEach((node, index) => {
    node.classList.toggle("active", index === stage);
    node.classList.toggle("complete", index < stage);
  });
  pipeLinks.forEach((link, index) => link.classList.toggle("complete", index < stage));
  feedLines.forEach((line, index) => line.classList.toggle("visible", index <= stage));
}

const storyObserver = new IntersectionObserver(
  (entries) => {
    const current = entries.find((entry) => entry.isIntersecting);
    if (current) selectStoryStage(Number(current.target.dataset.storyStage));
  },
  { rootMargin: "-30% 0px -50%", threshold: 0 },
);

storySteps.forEach((step) => storyObserver.observe(step));

const mobileStory = window.matchMedia("(max-width: 760px)");

function syncMobileStory(event) {
  if (event.matches) selectStoryStage(3);
}

mobileStory.addEventListener("change", syncMobileStory);
syncMobileStory(mobileStory);
