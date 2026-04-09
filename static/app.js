const state = {
  docs: [],
  selectedDocId: null,
  compareIds: new Set(),
};

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadList = document.getElementById('uploadList');
const libraryList = document.getElementById('libraryList');
const docTitle = document.getElementById('docTitle');
const summaryTab = document.getElementById('summaryTab');
const dataTab = document.getElementById('dataTab');

function initTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });
}

function formatSection(title, value) {
  const display = Array.isArray(value) ? `<ul>${value.map(v => `<li>${v}</li>`).join('')}</ul>` : `<p>${value ?? '-'}</p>`;
  return `<div class="section"><h3>${title}</h3>${display}</div>`;
}

function renderSummary(doc) {
  const s = doc.summary;
  docTitle.textContent = `${doc.custom_name} (${s.year || 'Unknown year'})`;
  summaryTab.innerHTML = [
    formatSection('Executive summary', s.executive_summary),
    formatSection('Main message of the article', s.main_message),
    formatSection('Why this paper matters', s.why_matters),
    formatSection('Key findings', s.key_findings),
    formatSection('Methods used', s.methods_used),
    formatSection('Materials / sample / setup', s.materials_setup),
    formatSection('Important numerical results', s.important_numerical_results),
    formatSection('Conclusions', s.conclusions),
    formatSection('Limitations / weaknesses', s.limitations),
    formatSection('What this means for Tetratherix', s.tetratherix_implications),
    formatSection('Suggested quote-worthy lines or evidence', s.quote_worthy),
    formatSection('3-bullet quick take', s.quick_take),
    formatSection('Confidence / certainty', s.confidence),
    `<div class="section"><h3>Relevance tags</h3>${(s.relevance_tags || []).map(t => `<span class="badge">${t}</span>`).join('')}</div>`
  ].join('');

  const d = s.extracted_data || {};
  dataTab.innerHTML = [
    formatSection('Study objective', d.study_objective),
    formatSection('Hypothesis', d.hypothesis),
    formatSection('Material composition', d.material_composition),
    formatSection('Test methods', d.test_methods),
    formatSection('Controls / comparison groups', d.controls),
    formatSection('Statistical significance', d.statistical_significance),
    formatSection('Performance outcomes', d.performance_outcomes),
    formatSection('Limitations', d.limitations),
    formatSection('Future work', d.future_work),
    formatSection('Claim strength', d.claim_strength),
  ].join('');
}

function applyFilters(docs) {
  const keyword = document.getElementById('keywordFilter').value.toLowerCase();
  const year = document.getElementById('yearFilter').value.trim();
  const type = document.getElementById('typeFilter').value;
  return docs.filter(doc => {
    const hay = `${doc.custom_name} ${(doc.summary.relevance_tags || []).join(' ')} ${doc.summary.executive_summary}`.toLowerCase();
    const yearMatch = !year || String(doc.summary.year || '').includes(year);
    const typeMatch = !type || doc.doc_type === type;
    return hay.includes(keyword) && yearMatch && typeMatch;
  });
}

function renderLibrary() {
  const docs = applyFilters(state.docs);
  libraryList.innerHTML = docs.map(doc => `
    <li>
      <label><input type="checkbox" data-compare="${doc.id}" ${state.compareIds.has(doc.id) ? 'checked' : ''} /> Compare</label>
      <strong>${doc.favorite ? '⭐' : ''} ${doc.custom_name}</strong><br>
      <small>${doc.filename} • ${doc.summary.year || 'n/a'} • ${doc.doc_type}</small><br>
      <button data-open="${doc.id}">Open</button>
      <button data-fav="${doc.id}">${doc.favorite ? 'Unfavourite' : 'Favourite'}</button>
      <button data-rename="${doc.id}">Rename</button>
      <span class="badge">${doc.status}</span>
    </li>
  `).join('');

  libraryList.querySelectorAll('[data-open]').forEach(btn => btn.onclick = () => selectDoc(btn.dataset.open));
  libraryList.querySelectorAll('[data-fav]').forEach(btn => btn.onclick = () => toggleFav(btn.dataset.fav));
  libraryList.querySelectorAll('[data-rename]').forEach(btn => btn.onclick = () => renameDoc(btn.dataset.rename));
  libraryList.querySelectorAll('[data-compare]').forEach(box => {
    box.onchange = () => box.checked ? state.compareIds.add(box.dataset.compare) : state.compareIds.delete(box.dataset.compare);
  });
}

async function fetchDocs() {
  const res = await fetch('/api/documents');
  state.docs = await res.json();
  renderLibrary();
  if (!state.selectedDocId && state.docs[0]) selectDoc(state.docs[0].id);
}

function selectDoc(id) {
  state.selectedDocId = id;
  const doc = state.docs.find(d => d.id === id);
  if (doc) renderSummary(doc);
}

async function upload() {
  const files = fileInput.files;
  if (!files.length) return;
  const form = new FormData();
  [...files].forEach(file => {
    const li = document.createElement('li');
    li.textContent = `${file.name} — Uploading...`;
    uploadList.appendChild(li);
    form.append('files', file);
  });

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/upload');
  xhr.upload.onprogress = evt => {
    const pct = evt.lengthComputable ? Math.round((evt.loaded / evt.total) * 100) : 0;
    uploadList.lastChild && (uploadList.lastChild.textContent = `Upload progress: ${pct}%`);
  };
  xhr.onload = async () => {
    await fetchDocs();
    uploadList.innerHTML += '<li>Analysis complete ✅</li>';
  };
  xhr.send(form);
}

async function toggleFav(id) {
  const doc = state.docs.find(d => d.id === id);
  const res = await fetch(`/api/documents/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ favorite: !doc.favorite })
  });
  const updated = await res.json();
  state.docs = state.docs.map(d => d.id === id ? updated : d);
  renderLibrary();
}

async function renameDoc(id) {
  const next = prompt('Rename article:');
  if (!next) return;
  const res = await fetch(`/api/documents/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ custom_name: next })
  });
  const updated = await res.json();
  state.docs = state.docs.map(d => d.id === id ? updated : d);
  renderLibrary();
  if (state.selectedDocId === id) renderSummary(updated);
}

async function askQuestion() {
  if (!state.selectedDocId) return;
  const question = document.getElementById('questionInput').value;
  const answerBox = document.getElementById('answerBox');
  answerBox.textContent = 'Thinking...';
  const res = await fetch('/api/ask', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: state.selectedDocId, question })
  });
  const data = await res.json();
  answerBox.innerHTML = `<strong>Answer (${data.confidence})</strong><p>${data.answer}</p>`;
}

async function compareDocs() {
  const ids = [...state.compareIds];
  const output = document.getElementById('comparisonOutput');
  output.textContent = 'Comparing...';
  const res = await fetch('/api/compare', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  });
  const data = await res.json();
  output.innerHTML = data.map(item => `
    <div class="section">
      <h3>${item.name}</h3>
      <p><strong>Objective:</strong> ${item.objective}</p>
      <p><strong>Material/system:</strong> ${item.material_system}</p>
      <p><strong>Methods:</strong> ${item.methods}</p>
      <p><strong>Strengths:</strong> ${(item.strengths || []).join('; ')}</p>
      <p><strong>Weaknesses:</strong> ${item.weaknesses}</p>
      <p><strong>Tetratherix relevance:</strong> ${item.tetratherix_relevance}</p>
    </div>
  `).join('');
}

function exportCurrent(kind) {
  if (!state.selectedDocId) return;
  if (kind === 'pdf') {
    window.print();
    return;
  }
  window.open(`/api/export/${state.selectedDocId}/${kind}`, '_blank');
}

function copySummary() {
  const text = summaryTab.innerText;
  navigator.clipboard.writeText(text);
}

uploadBtn.onclick = upload;
document.getElementById('askBtn').onclick = askQuestion;
document.getElementById('compareBtn').onclick = compareDocs;
document.getElementById('copySummaryBtn').onclick = copySummary;
document.getElementById('exportWordBtn').onclick = () => exportCurrent('doc');
document.getElementById('exportCsvBtn').onclick = () => exportCurrent('csv');
document.getElementById('exportPdfBtn').onclick = () => exportCurrent('pdf');
['keywordFilter', 'yearFilter', 'typeFilter'].forEach(id => document.getElementById(id).oninput = renderLibrary);

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragging'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragging');
  fileInput.files = e.dataTransfer.files;
});

initTabs();
fetchDocs();
