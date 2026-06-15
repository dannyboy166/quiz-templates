/* Image generation client-side JS */

async function generateQuestionImage(itemId) {
    const btn = document.getElementById('gen-question-btn');
    const previewDiv = document.getElementById('question-image-preview');
    const prompt = document.getElementById('question-prompt').value;

    btn.disabled = true;
    previewDiv.innerHTML = '<div class="generating-overlay"><span class="spinner"></span> Generating image...</div>';

    try {
        const res = await fetch(`/api/images/generate/${itemId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt: prompt})
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
            badge.textContent = data.pushed ? 'Approved + Pushed to Airtable' : 'Approved';
        }
        if (data.push_error) {
            alert('Approved but Airtable push failed: ' + data.push_error);
        }
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

    // Collect prompts — use custom if typed, otherwise use default template
    const prompts = {};
    for (const id of ids) {
        const input = document.getElementById(`prompt-${id}`);
        const customPrompt = input ? input.value.trim() : '';

        if (customPrompt) {
            prompts[id] = customPrompt;
        } else if (defaultTemplate) {
            // Find the question text for this ID
            const q = ALL_QUESTIONS.find(q => q.id === id);
            const questionText = q ? q.text : '';
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
            body: JSON.stringify({item_ids: ids, prompts: prompts})
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
                window.location.reload();
            }, 1500);
        }
    } catch (e) {
        setTimeout(pollImageBulkStatus, 3000);
    }
}
