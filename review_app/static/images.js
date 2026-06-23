/* Image generation client-side JS */

async function generateQuestionImage(itemId) {
    const btn = document.getElementById('gen-question-btn');
    const previewDiv = document.getElementById('question-image-preview');
    const prompt = document.getElementById('question-prompt').value;
    const sizeEl = document.getElementById('image-size') || document.getElementById('detail-image-size');
    const size = sizeEl ? sizeEl.value : '1024x1024';

    btn.disabled = true;
    previewDiv.innerHTML = '<div class="generating-overlay"><span class="spinner"></span> Generating image...</div>';

    try {
        const res = await fetch(`/api/images/generate/${itemId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt: prompt, size: size})
        });
        const data = await res.json();
        if (data.ok) {
            previewDiv.innerHTML = `<img class="image-preview" src="/generated-images/${itemId}-question.png?t=${Date.now()}" alt="Generated question image">`;
            btn.textContent = 'Regenerate';
            // Enable approve button
            const approveBtn = document.getElementById('approve-question-btn');
            if (approveBtn) approveBtn.disabled = false;
        } else {
            previewDiv.innerHTML = `<div class="no-image">Error: ${data.error || 'Unknown error'}</div>`;
        }
    } catch (e) {
        previewDiv.innerHTML = `<div class="no-image">Error: ${e.message}</div>`;
    }
    btn.disabled = false;
}

async function generateAnswerImage(itemId, optionNum) {
    const btn = document.getElementById(`gen-answer-${optionNum}-btn`);
    const previewDiv = document.getElementById(`answer-${optionNum}-preview`);
    const prompt = document.getElementById(`answer-${optionNum}-prompt`).value;

    btn.disabled = true;
    previewDiv.innerHTML = '<div class="generating-overlay"><span class="spinner"></span> Generating...</div>';

    try {
        const res = await fetch(`/api/images/generate-answer/${itemId}/${optionNum}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt: prompt})
        });
        const data = await res.json();
        if (data.ok) {
            previewDiv.innerHTML = `<img class="image-preview" src="/generated-images/${itemId}-answer${optionNum}.png?t=${Date.now()}" alt="Generated answer ${optionNum} image">`;
            btn.textContent = 'Regenerate';
        } else {
            previewDiv.innerHTML = `<div class="no-image">Error: ${data.error || 'Unknown error'}</div>`;
        }
    } catch (e) {
        previewDiv.innerHTML = `<div class="no-image">Error: ${e.message}</div>`;
    }
    btn.disabled = false;
}

async function generateAllAnswerImages(itemId) {
    const btn = document.getElementById('gen-all-answers-btn');
    btn.disabled = true;
    btn.textContent = 'Generating...';

    for (let i = 1; i <= 4; i++) {
        const promptEl = document.getElementById(`answer-${i}-prompt`);
        if (!promptEl || !promptEl.value.trim()) continue;
        await generateAnswerImage(itemId, i);
    }

    btn.disabled = false;
    btn.textContent = 'Generate All Answer Images';
}

async function approveImage(itemId, imageType, optionNum) {
    const body = {image_type: imageType};
    if (optionNum) body.option_num = optionNum;

    const res = await fetch(`/api/images/approve/${itemId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    });
    const data = await res.json();
    if (data.ok) {
        const badge = document.querySelector('.status-badge');
        if (badge) {
            badge.className = 'status-badge status-approved';
            badge.textContent = data.canva_uploaded ? 'Approved + Sent to Canva' : 'Approved';
        }
        if (data.canva_error) {
            alert('Approved but Canva upload failed: ' + data.canva_error);
        }
    }
}

async function editQuestionImage(itemId) {
    const editInput = document.getElementById('edit-instruction');
    const instruction = editInput ? editInput.value.trim() : '';
    if (!instruction) {
        alert('Type an edit instruction (e.g. "remove the text", "make background white")');
        if (editInput) editInput.focus();
        return;
    }

    const btn = document.getElementById('edit-question-btn');
    const previewDiv = document.getElementById('question-image-preview');
    const sizeEl = document.getElementById('detail-image-size') || document.getElementById('image-size');
    const size = sizeEl ? sizeEl.value : '1024x1024';

    btn.disabled = true;
    btn.textContent = 'Editing...';
    previewDiv.innerHTML = '<div class="generating-overlay"><span class="spinner"></span> Editing image...</div>';

    try {
        const res = await fetch(`/api/images/edit/${itemId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt: instruction, size: size})
        });
        const data = await res.json();
        if (data.ok) {
            previewDiv.innerHTML = `<img class="image-preview" src="/generated-images/${itemId}-question.png?t=${Date.now()}" alt="Edited question image">`;
            const badge = document.querySelector('.status-badge');
            if (badge) { badge.className = 'status-badge status-pending'; badge.textContent = 'Edited — needs approval'; }
            editInput.value = '';
            loadVersions(itemId);
        } else {
            previewDiv.innerHTML = `<div class="no-image">Error: ${data.error || 'Unknown error'}</div>`;
        }
    } catch (e) {
        previewDiv.innerHTML = `<div class="no-image">Error: ${e.message}</div>`;
    }
    btn.disabled = false;
    btn.textContent = 'Edit Image';
}

async function loadVersions(itemId) {
    const container = document.getElementById('version-history');
    if (!container) return;

    try {
        const res = await fetch(`/api/images/versions/${itemId}`);
        const data = await res.json();
        if (!data.versions || data.versions.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem;">No previous versions yet.</p>';
            return;
        }
        container.innerHTML = '<h3 style="margin-bottom:0.5rem;">Previous Versions</h3>' +
            '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
            data.versions.map((v, i) => `
                <div style="text-align:center;cursor:pointer;" onclick="restoreVersion('${itemId}', ${i+1})">
                    <img src="${v.url}?t=${Date.now()}" style="width:100px;height:100px;object-fit:cover;border-radius:6px;border:2px solid #ddd;">
                    <div style="font-size:0.75rem;color:var(--text-muted);">v${i+1}</div>
                </div>
            `).join('') +
            '</div>';
    } catch (e) {
        container.innerHTML = '';
    }
}

async function restoreVersion(itemId, versionNum) {
    if (!confirm(`Restore version ${versionNum}? Current image will be archived.`)) return;

    try {
        const res = await fetch(`/api/images/restore-version/${itemId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({version: versionNum})
        });
        const data = await res.json();
        if (data.ok) {
            const previewDiv = document.getElementById('question-image-preview');
            if (previewDiv) {
                previewDiv.innerHTML = `<img class="image-preview" src="/generated-images/${itemId}-question.png?t=${Date.now()}" alt="Restored question image">`;
            }
            const badge = document.querySelector('.status-badge');
            if (badge) { badge.className = 'status-badge status-pending'; badge.textContent = 'Restored — needs approval'; }
            loadVersions(itemId);
        } else {
            alert('Error: ' + (data.error || 'Unknown'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function flagImage(itemId) {
    const note = prompt("What's the issue? (optional)");
    if (note === null) return;

    const res = await fetch(`/api/images/flag/${itemId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({note: note})
    });
    const data = await res.json();
    if (data.ok) {
        const badge = document.querySelector('.status-badge');
        if (badge) {
            badge.className = 'status-badge status-flagged';
            badge.textContent = 'Flagged';
        }
    }
}

async function savePrompt(itemId, imageType, optionNum) {
    const promptId = imageType === 'question'
        ? 'question-prompt'
        : `answer-${optionNum}-prompt`;
    const prompt = document.getElementById(promptId).value;

    await fetch(`/api/images/save-prompt/${itemId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({image_type: imageType, option_num: optionNum, prompt: prompt})
    });
}

async function pushToAirtable(itemId, imageType, optionNum) {
    const btnId = imageType === 'question'
        ? 'push-question-btn'
        : `push-answer-${optionNum}-btn`;
    const btn = document.getElementById(btnId);
    btn.disabled = true;
    btn.textContent = 'Pushing...';

    try {
        const res = await fetch(`/api/images/push-airtable/${itemId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({image_type: imageType, option_num: optionNum})
        });
        const data = await res.json();
        if (data.ok) {
            btn.textContent = 'Pushed!';
            btn.classList.remove('btn-airtable');
            btn.classList.add('btn-success');
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
            btn.disabled = false;
            btn.textContent = 'Push to Airtable';
        }
    } catch (e) {
        alert('Error: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Push to Airtable';
    }
}

// Bulk generation for image list page — sends prompts from the list inputs
async function bulkGenerateImages() {
    const ids = Array.from(selected);
    if (!ids.length) return;

    // Get default prompt template
    const templateEl = document.getElementById('default-prompt-template');
    const defaultTemplate = templateEl ? templateEl.value.trim() : '';

    // Base style prepended to per-row prompts (same as in image_list.html resolvePrompt)
    const BASE_STYLE = "For a children's educational quiz. Simple, colorful cartoon style. No text or writing in the image.";

    // Collect prompts — use custom if typed, otherwise use default template
    // {question} gets replaced with actual question text in both cases
    const prompts = {};
    for (const id of ids) {
        const input = document.getElementById(`prompt-${id}`);
        const customPrompt = input ? input.value.trim() : '';
        const q = ALL_QUESTIONS.find(q => q.id === id);
        const questionText = q ? q.text : '';

        if (customPrompt) {
            const resolved = customPrompt.replace('{question}', questionText);
            prompts[id] = `${BASE_STYLE} ${resolved}`;
        } else if (defaultTemplate) {
            prompts[id] = defaultTemplate.replace('{question}', questionText);
        }
    }

    const btn = document.getElementById('bulk-gen-btn');
    btn.disabled = true;
    btn.textContent = 'Starting...';

    try {
        const res = await fetch('/api/images/bulk-generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item_ids: ids, prompts: prompts, size: document.getElementById('image-size')?.value || '1024x1024'})
        });
        const data = await res.json();
        if (data.ok) {
            showImageBulkProgress();
            pollImageBulkStatus();
        }
    } catch (e) {
        alert('Error: ' + e.message);
        btn.disabled = false;
        btn.textContent = `Generate Selected (${selected.size})`;
    }
}

function showImageBulkProgress() {
    document.getElementById('bulk-progress').style.display = 'block';
    const indicator = document.getElementById('image-bulk-indicator');
    if (indicator) indicator.style.display = 'flex';
}

function hideImageBulkProgress() {
    document.getElementById('bulk-progress').style.display = 'none';
    const indicator = document.getElementById('image-bulk-indicator');
    if (indicator) indicator.style.display = 'none';
    const btn = document.getElementById('bulk-gen-btn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = `Generate Selected (${selected.size})`;
    }
}

async function pollImageBulkStatus() {
    try {
        const res = await fetch('/api/images/bulk-status');
        const data = await res.json();

        const pct = data.total > 0 ? (data.completed / data.total * 100) : 0;
        document.getElementById('bulk-progress-bar').style.width = pct + '%';
        document.getElementById('bulk-progress-text').textContent =
            `${data.completed} / ${data.total}` +
            (data.errors.length ? ` (${data.errors.length} errors)` : '');

        const indicatorText = document.getElementById('image-bulk-indicator-text');
        if (indicatorText) indicatorText.textContent = `Generating ${data.completed}/${data.total}...`;

        if (data.running) {
            setTimeout(pollImageBulkStatus, 2000);
        } else {
            if (indicatorText) indicatorText.textContent = 'Done!';
            setTimeout(() => {
                hideImageBulkProgress();
                // Update generated status for completed items without reloading the page
                // so Georgia stays on her current filtered view and scroll position
                for (const id of selected) {
                    const q = ALL_QUESTIONS.find(q => q.id === id);
                    if (q) q.has_gen_image = true;
                }
                selected.clear();
                renderTable();
            }, 1500);
        }
    } catch (e) {
        setTimeout(pollImageBulkStatus, 3000);
    }
}
