const state = {
  snapshot: null,
  busy: false,
  highlightedBits: [],
  activeLeaf: null,
  activeRoot: false,
  activePage: null,
  cachePage: null,
  falsePositive: false,
};

const elements = {
  form: document.querySelector("#record-form"),
  key: document.querySelector("#key-input"),
  value: document.querySelector("#value-input"),
  status: document.querySelector("#status-line"),
  bloom: document.querySelector("#bloom-grid"),
  root: document.querySelector("#tree-root"),
  rootKeys: document.querySelector("#root-keys"),
  leaves: document.querySelector("#tree-leaves"),
  cache: document.querySelector("#cache-slots"),
  disk: document.querySelector("#disk-pages"),
  diskCount: document.querySelector("#disk-count"),
  benchmark: document.querySelector("#benchmark-rows"),
  benchmarkNote: document.querySelector("#benchmark-note"),
  buttons: [...document.querySelectorAll(".actions button")],
};

const wait = (milliseconds = 580) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function setStatus(message, tone = "") {
  elements.status.className = `status-line${tone ? ` is-${tone}` : ""}`;
  elements.status.querySelector("p").textContent = message;
}

function setBusy(busy) {
  state.busy = busy;
  elements.buttons.forEach((button) => { button.disabled = busy; });
}

function addKeys(container, keys) {
  if (!keys.length) {
    const empty = document.createElement("span");
    empty.className = "empty-note";
    empty.textContent = "empty";
    container.append(empty);
    return;
  }
  keys.forEach((key) => {
    const chip = document.createElement("span");
    chip.className = "tree-key";
    chip.textContent = key;
    container.append(chip);
  });
}

function renderBloom(bits = state.snapshot?.bloom_bits || []) {
  elements.bloom.replaceChildren();
  bits.forEach((bit, index) => {
    const cell = document.createElement("span");
    cell.className = `bit-cell${bit ? " is-set" : ""}${state.highlightedBits.includes(index) ? " is-checked" : ""}`;
    cell.textContent = bit;
    cell.title = `Bit ${index}: ${bit}`;
    cell.setAttribute("aria-label", `Bit ${index}: ${bit}${state.highlightedBits.includes(index) ? ", checked" : ""}`);
    elements.bloom.append(cell);
  });
}

function renderTree(snapshot = state.snapshot) {
  if (!snapshot) return;
  elements.rootKeys.replaceChildren();
  addKeys(elements.rootKeys, snapshot.root_keys);
  elements.root.className = `tree-node root-node${state.activeRoot ? " is-active" : ""}`;
  elements.leaves.replaceChildren();
  snapshot.leaves.forEach((leaf) => {
    const node = document.createElement("div");
    const keys = document.createElement("div");
    keys.className = "leaf-keys";
    const caption = document.createElement("span");
    caption.className = "node-caption";
    caption.textContent = "Leaf";
    if (leaf.keys.length) {
      leaf.keys.forEach((key, index) => {
        const entry = document.createElement("span");
        entry.className = "leaf-entry";
        const keyChip = document.createElement("span");
        keyChip.className = "tree-key";
        keyChip.textContent = key;
        const pageLabel = document.createElement("span");
        pageLabel.className = "leaf-page";
        pageLabel.textContent = `to page ${leaf.pages[index]}`;
        entry.append(keyChip, pageLabel);
        keys.append(entry);
      });
    } else {
      addKeys(keys, leaf.keys);
    }
    const isActive = state.activeLeaf === JSON.stringify(leaf.keys);
    node.className = `tree-node leaf-node${isActive ? " is-active" : ""}${state.falsePositive && isActive ? " is-error" : ""}`;
      node.append(caption, keys);
    elements.leaves.append(node);
  });
}

function renderCache(snapshot = state.snapshot) {
  if (!snapshot) return;
  elements.cache.replaceChildren();
  const pages = snapshot.cache_pages;
  for (let index = 0; index < snapshot.cache_capacity; index += 1) {
    const page = pages[index];
    const slot = document.createElement("div");
    slot.className = `cache-slot${page === undefined ? "" : " has-page"}${page === state.cachePage ? " is-active" : ""}`;
    const label = document.createElement("span");
    label.className = "slot-label";
    label.textContent = index === 0 ? "Oldest" : index === snapshot.cache_capacity - 1 ? "Newest" : `Slot ${index + 1}`;
    const value = document.createElement("span");
    value.className = "slot-page";
    value.textContent = page === undefined ? "—" : `Page ${page}`;
    slot.append(label, value);
    elements.cache.append(slot);
  }
}

function renderDisk(snapshot = state.snapshot) {
  if (!snapshot) return;
  elements.disk.replaceChildren();
  elements.diskCount.textContent = `${snapshot.page_count} ${snapshot.page_count === 1 ? "page" : "pages"}`;
  if (!snapshot.pages.length) {
    const empty = document.createElement("p");
    empty.className = "empty-note";
    empty.textContent = "No pages written yet.";
    elements.disk.append(empty);
    return;
  }
  snapshot.pages.forEach((page) => {
    const card = document.createElement("article");
    card.className = `disk-page${page.page_number === state.activePage ? " is-active" : ""}${page.page_number === state.cachePage ? " is-cached" : ""}${page.deleted ? " is-deleted" : ""}`;
    const title = document.createElement("p");
    title.className = "disk-page-title";
    title.textContent = `Page ${page.page_number}${page.deleted ? " · deleted" : ""}`;
    const record = document.createElement("div");
    record.className = "disk-record";
    const key = document.createElement("span");
    key.textContent = page.deleted ? `${page.key} ×` : `${page.key} :`;
    const value = document.createElement("span");
    value.textContent = page.deleted ? "tombstone" : page.value;
    record.append(key, value);
    card.append(title, record);
    elements.disk.append(card);
  });
}

function renderBenchmark(benchmark) {
  if (!benchmark) return;
  const labels = [
    ["full_scan", "Page scan"],
    ["bplus_tree", "B+ Tree"],
    ["tree_and_cache", "Tree + cache"],
  ];
  const times = benchmark.milliseconds_per_lookup;
  const maximum = Math.max(...Object.values(times), 0.001);
  elements.benchmark.replaceChildren();
  labels.forEach(([id, label]) => {
    const row = document.createElement("div");
    row.className = "benchmark-row";
    const name = document.createElement("span");
    name.className = "benchmark-label";
    name.textContent = label;
    const track = document.createElement("div");
    track.className = "bar-track";
    track.setAttribute("role", "img");
    track.setAttribute("aria-label", `${label}: ${times[id].toFixed(3)} milliseconds per lookup`);
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${Math.max(2, (times[id] / maximum) * 100)}%`;
    track.append(fill);
    const value = document.createElement("span");
    value.className = "benchmark-value";
    value.textContent = `${times[id].toFixed(3)} ms`;
    row.append(name, track, value);
    elements.benchmark.append(row);
  });
  elements.benchmarkNote.textContent = `${benchmark.records.toLocaleString()} records · ${benchmark.queries} lookups`;
}

function renderState(snapshot) {
  state.snapshot = snapshot;
  renderBloom();
  renderTree();
  renderCache();
  renderDisk();
  renderBenchmark(snapshot.benchmark);
}

async function refreshState() {
  renderState(await request("/api/state"));
}

function getKey() {
  const key = Number(elements.key.value);
  if (!elements.key.value || !Number.isSafeInteger(key)) throw new Error("Enter a whole-number key.");
  return key;
}

async function animateGet() {
  if (state.busy) return;
  try {
    const key = getKey();
    setBusy(true);
    state.highlightedBits = [];
    state.activeRoot = false;
    state.activeLeaf = null;
    state.activePage = null;
    state.cachePage = null;
    state.falsePositive = false;
    const result = await request(`/api/get?key=${encodeURIComponent(key)}`);
    const trace = result.trace;

    state.highlightedBits = trace.bloom.checked_bits;
    renderBloom(trace.bloom.bits);
    setStatus(`The Bloom filter checked bits ${trace.bloom.checked_bits.join(" and ")}. ${trace.bloom.present ? "Both are set, so the key may be present." : "At least one bit is clear, so the key is definitely absent."}`, "bloom");
    await wait();

    if (!trace.bloom.present) {
      setStatus(`Key ${key} is definitely not present. The B+ Tree and disk were not read.`, "bloom");
      await refreshState();
      return;
    }

    const treeSteps = trace.tree_path;
    const internalSteps = treeSteps.filter((step) => step.type === "internal");
    for (let index = 0; index < internalSteps.length; index += 1) {
      state.activeRoot = index === 0;
      renderTree();
      const step = internalSteps[index];
      setStatus(index === 0
        ? `At the root, separators ${step.keys.join(", ") || "(none)"} route key ${key} through child ${step.child + 1}.`
        : `The index follows child ${step.child + 1} through separators ${step.keys.join(", ") || "(none)"}.`, "");
      await wait();
    }

    const leafStep = treeSteps.at(-1);
    const leaf = state.snapshot.leaves.find((candidate) => JSON.stringify(candidate.keys) === JSON.stringify(leafStep?.keys));
    state.activeLeaf = leaf ? JSON.stringify(leaf.keys) : null;
    state.activeRoot = false;
    state.falsePositive = !trace.found_in_tree;
    renderTree();
    if (trace.found_in_tree) {
      setStatus(`Leaf keys ${leafStep.keys.join(", ") || "(empty)"} contain key ${key}, stored at page ${trace.page_number}.`);
    } else {
      setStatus(`False positive: the Bloom filter said maybe, but leaf keys ${leafStep.keys.join(", ") || "(empty)"} do not contain key ${key}.`, "error");
      await wait();
      await refreshState();
      return;
    }
    await wait();

    state.cachePage = trace.page_number;
    renderCache();
    if (trace.cache_hit) {
      setStatus(`Cache hit: page ${trace.page_number} was already in the LRU cache. No disk read was needed.`, "cache");
    } else {
      const eviction = trace.evicted_page === null ? "No page was evicted." : `Page ${trace.evicted_page} was evicted.`;
      setStatus(`Cache miss: read page ${trace.page_number} from disk and added it to the cache. ${eviction}`, "disk");
    }
    await wait();

    state.activePage = trace.page_number;
    renderDisk();
    setStatus(result.value === null ? `Key ${key} has no value.` : `Read key ${key}: “${result.value}”.`, trace.cache_hit ? "cache" : "disk");
    await refreshState();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function writeRecord() {
  if (state.busy) return;
  try {
    const key = getKey();
    if (!elements.value.value) throw new Error("Enter a text value to put.");
    setBusy(true);
    const result = await request("/api/put", {
      method: "POST",
      body: JSON.stringify({ key, value: elements.value.value }),
    });
    state.activePage = result.page_number;
    state.cachePage = result.page_number;
    setStatus(`Put key ${key} on page ${result.page_number}. The index and Bloom filter are ready for the next lookup.`, "bloom");
    await refreshState();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function deleteRecord() {
  if (state.busy) return;
  try {
    const key = getKey();
    setBusy(true);
    const result = await request("/api/delete", {
      method: "POST",
      body: JSON.stringify({ key }),
    });
    state.activePage = null;
    state.cachePage = null;
    setStatus(result.ok
      ? `Deleted key ${key}. Its page remains as a tombstone, and Bloom bits are intentionally not cleared.`
      : `Key ${key} was not found, so nothing was deleted.`, result.ok ? "bloom" : "error");
    await refreshState();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function resetDatabase() {
  if (state.busy) return;
  try {
    setBusy(true);
    await request("/api/reset", { method: "POST", body: "{}" });
    state.highlightedBits = [];
    state.activeRoot = false;
    state.activeLeaf = null;
    state.activePage = null;
    state.cachePage = null;
    state.falsePositive = false;
    await refreshState();
    setStatus("Database reset. The data file, index, Bloom filter and cache are empty.");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

document.querySelector("#get-button").addEventListener("click", animateGet);
document.querySelector("#put-button").addEventListener("click", writeRecord);
document.querySelector("#delete-button").addEventListener("click", deleteRecord);
document.querySelector("#reset-button").addEventListener("click", resetDatabase);
elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  animateGet();
});

refreshState().catch((error) => setStatus(`Could not connect to the database: ${error.message}`, "error"));