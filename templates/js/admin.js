import { getCookie, setCookie } from "{{ url_for('serve_js', filename='utils.js') }}";

(() => {

  const refreshTablesButton = document.getElementById("refreshTablesButton");
  const refreshTablesTime= document.getElementById("refreshTablesTime");

  const jobsTableBody = document.getElementById("jobsTableBody");
  const jobQueue = document.getElementById("jobQueue");
  const minersTableBody = document.getElementById("minersTableBody");
  const friendbotsTableBody = document.getElementById("friendbotsTableBody");

  const jobFilter = document.getElementById("jobFilter");

  let jobsData;
  let jobStrings;
  let minersData;
  let friendbotsData;

  const inspectedJobs = new Set();


  async function refreshTables() {
    refreshJobs();
    refreshMiners();
    refreshFriendbots();
    refreshTablesTime.innerText = new Date().toLocaleTimeString();
  }

  async function refreshJobs() {
    const response = await fetch("{{ url_for('api_admin_list_jobs') }}");
    const responseJson = await response.json();
    if (response.ok) {
      if (responseJson.result != "success") {
        window.alert(responseJson.message);
        return;
      }
      jobsData = responseJson.data;
      jobStrings = jobsData.jobs.map(job => JSON.stringify(job));
      updateJobsTable();
      updateJobsQueue();
    } else {
      window.alert("Error retrieving jobs: " + responseJson.message);
    }
  }

  async function refreshMiners() {
    const response = await fetch("{{ url_for('api_admin_list_miners') }}");
    const responseJson = await response.json();
    if (response.ok) {
      if (responseJson.result != "success") {
        window.alert(responseJson.message);
        return;
      }
      minersData = responseJson.data.miners;
      updateMinersTable();
    } else {
      window.alert("Error retrieving miners: " + responseJson.message);
    }
  }

  async function refreshFriendbots() {
    const response = await fetch("{{ url_for('api_admin_list_friendbots') }}");
    const responseJson = await response.json();
    if (response.ok) {
      if (responseJson.result != "success") {
        window.alert(responseJson.message);
        return;
      }
      friendbotsData = responseJson.data.friendbots;
      updateFriendbotsTable();
    } else {
      window.alert("Error retrieving miners: " + responseJson.message);
    }
  }

  function updateJobsTable() {
    jobsTableBody.innerHTML = "";
    for (let i = 0; i < jobsData.jobs.length; i++) {
      const job = jobsData.jobs[i];
      const jobStr = jobStrings[i];
      if (!jobFilter.value || jobStr.includes(jobFilter.value)) {
        jobsTableBody.appendChild(createJobRow(job));
        if (inspectedJobs.has(job.key)) {
          jobsTableBody.appendChild(createJobInspectRow(job));
        }
      }
    }
  }

  function updateJobsQueue() {
    if (jobsData.queue.length) {
      jobQueue.innerHTML = jobsData.queue.join("\n");
    } else {
      jobQueue.innerText = "<empty>";
    }
  }

  function updateMinersTable() {
    minersTableBody.innerHTML = "";
    for (let miner of minersData) {
      minersTableBody.appendChild(createWorkerRow(miner));
    }
  }

  function updateFriendbotsTable() {
    friendbotsTableBody.innerHTML = "";
    for (let friendbot of friendbotsData) {
      friendbotsTableBody.appendChild(createWorkerRow(friendbot));
    }
  }

  function createJobRow(job) {
    const row = document.createElement("tr");
    row.className = "align-middle";

    const idCell = document.createElement("td");
    idCell.innerText = job.key;
    row.appendChild(idCell);

    const typeCell = document.createElement("td");
    typeCell.innerText = job.type;
    row.appendChild(typeCell);

    const statusCell = document.createElement("td");
    statusCell.innerText = job.status;
    row.appendChild(statusCell);

    const createdCell = document.createElement("td");
    const createDate = new Date(job.created);
    createdCell.innerText = createDate.toLocaleString();
    row.appendChild(createdCell);

    const updatedCell = document.createElement("td");
    const updateDate = new Date(job.last_update);
    updatedCell.innerText = updateDate.toLocaleString();
    row.appendChild(updatedCell);

    const assigneeCell = document.createElement("td");
    assigneeCell.innerText = job.assignee;
    row.appendChild(assigneeCell);

    const actionsCell = document.createElement("td");

    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    const cancelIcon = document.createElement("i");
    cancelButton.appendChild(cancelIcon);
    const cancelText = document.createElement("div");
    cancelText.className = "visually-hidden";
    if ("canceled" === job.status) {
      cancelButton.addEventListener("click", event => resetJob(job.key));
      cancelButton.title = "Reset job";
      cancelButton.className = "btn btn-warning px-2";
      cancelIcon.className = "fa-solid fa-fw fa-arrow-rotate-left";
      cancelText.innerText = "Reset job";
    } else {
      cancelButton.addEventListener("click", event => cancelJob(job.key));
      cancelButton.title = "Cancel job";
      cancelButton.className = "btn btn-danger px-2";
      cancelIcon.className = "fa-solid fa-fw fa-xmark";
      cancelText.innerText = "Cancel job";
    }
    cancelButton.appendChild(cancelText);
    actionsCell.appendChild(cancelButton);

    actionsCell.appendChild(document.createTextNode(" "));

    const inspectButton = document.createElement("button");
    inspectButton.addEventListener("click", event => inspectJob(job.key));
    inspectButton.type = "button";
    inspectButton.className = "btn btn-primary px-2";
    inspectButton.title = "Inspect job";
    const inspectIcon = document.createElement("i");
    inspectIcon.className = "fa-solid fa-fw fa-magnifying-glass";
    inspectButton.appendChild(inspectIcon);
    const inspectText = document.createElement("div");
    inspectText.className = "visually-hidden";
    inspectText.innerText = "Inspect job";
    inspectButton.appendChild(inspectText);
    actionsCell.appendChild(inspectButton);

    row.appendChild(actionsCell);

    return row;
  }

  function createJobInspectRow(job) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;

    const jobJsonOuter = document.createElement("pre");
    jobJsonOuter.className = "m-1";
    const jobJsonInner = document.createElement("code");

    jobJsonInner.innerText = JSON.stringify(job, null, 2);

    jobJsonOuter.appendChild(jobJsonInner);
    cell.appendChild(jobJsonOuter);

    row.appendChild(cell);
    return row;
  }

  function createWorkerRow(worker) {
    const row = document.createElement("tr");
    row.className = "align-middle";

    const nameCell = document.createElement("td");
    nameCell.innerText = worker.name;
    row.appendChild(nameCell);

    const ipCell = document.createElement("td");
    ipCell.innerText = worker.ip;
    row.appendChild(ipCell);

    const versionCell = document.createElement("td");
    versionCell.innerText = worker.version;
    row.appendChild(versionCell);

    const updatedCell = document.createElement("td");
    const updateDate = new Date(worker.last_update);
    updatedCell.innerText = updateDate.toLocaleString();
    row.appendChild(updatedCell);

    return row;
  }


  async function cancelJob(key) {
    let response;
    try {
      response = await fetch("{{ url_for('api_cancel_job', key='') }}" + key);
      const responseJson = await response.json();
      if (!response.ok) {
        throw new Error(responseJson.message);
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        // syntax error from parsing non-JSON server error response
        window.alert(`Error canceling job: ${response.status} - ${response.statusText}`);
      } else {
        // generic error
        window.alert(`Error canceling job: ${error.message}`);
      }
    }
    refreshJobs();
  }

  async function resetJob(key) {
    let response;
    try {
      response = await fetch("{{ url_for('api_reset_job', key='') }}" + key);
      const responseJson = await response.json();
      if (!response.ok) {
        throw new Error(responseJson.message);
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        // syntax error from parsing non-JSON server error response
        window.alert(`Error resetting job: ${response.status} - ${response.statusText}`);
      } else {
        // generic error
        window.alert(`Error resetting job: ${error.message}`);
      }
    }
    refreshJobs();
  }

  async function inspectJob(key) {
    if (inspectedJobs.has(key)) {
      inspectedJobs.delete(key);
    } else {
      inspectedJobs.add(key);
    }
    updateJobsTable();
  }

  document.addEventListener('DOMContentLoaded', () => {
    // event listeners
    refreshTablesButton.addEventListener("click", event => refreshTables());
    jobFilter.addEventListener("input", event => updateJobsTable());

    // tables refresh
    refreshTables();
    setInterval(refreshTables, 15000);
  });

})();
