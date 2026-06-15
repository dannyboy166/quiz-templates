/* QuestionReview client-side JS */

// Bulk generation — handles both questions and hints
async function bulkGenerate() {
    const questionIds = [];
    const hintJobs = [];

    for (const key of selected) {
        if (key.includes(':hint')) {
            const [itemId, hintPart] = key.split(':');
            const hintNum = parseInt(hintPart.replace('hint', ''));
            hintJobs.push({item_id: itemId, hint_num: hintNum});
        } else {
            questionIds.push(key);
        }
    }

    const btn = document.getElementById('bulk-gen-btn');
    btn.disabled = true;
    btn.textContent = 'Starting...';

    try {
        const res = await fetch('/api/bulk-generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item_ids: questionIds, hint_jobs: hintJobs})
        });
        const data = await res.json();
        if (data.ok) {
            showBulkProgress();
            pollBulkStatus();
        }
    } catch (e) {
        alert('Error starting bulk generation: ' + e.message);
        btn.disabled = false;
        btn.textContent = `Generate Selected (${selected.size})`;
    }
}

function showBulkProgress() {
    document.getElementById('bulk-progress').style.display = 'block';
    document.getElementById('bulk-indicator').style.display = 'flex';
}

function hideBulkProgress() {
    document.getElementById('bulk-progress').style.display = 'none';
    document.getElementById('bulk-indicator').style.display = 'none';
    const btn = document.getElementById('bulk-gen-btn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = `Generate Selected (${selected.size})`;
    }
}

async function pollBulkStatus() {
    try {
        const res = await fetch('/api/bulk-status');
        const data = await res.json();

        const pct = data.total > 0 ? (data.completed / data.total * 100) : 0;
        const typeLabel = data.current_type === 'hint' ? ' (hints)' : '';
        document.getElementById('bulk-progress-bar').style.width = pct + '%';
        document.getElementById('bulk-progress-text').textContent =
            `${data.completed} / ${data.total}${typeLabel}` +
            (data.errors.length ? ` (${data.errors.length} errors)` : '');
        document.getElementById('bulk-indicator-text').textContent =
            `Generating ${data.completed}/${data.total}${typeLabel}...`;

        if (data.running) {
            setTimeout(pollBulkStatus, 2000);
        } else {
            document.getElementById('bulk-indicator-text').textContent = 'Done!';
            setTimeout(() => {
                hideBulkProgress();
                // Refresh keeping filters
                const params = new URLSearchParams();
                const subject = document.getElementById('filter-subject');
                const status = document.getElementById('filter-status');
                const topic = document.getElementById('filter-topic');
                const sheet = document.getElementById('filter-sheet');
                const hints = document.getElementById('show-hints');
                if (subject && subject.value) params.set('subject', subject.value);
                if (status) params.set('status', status.value);
                if (topic && topic.value) params.set('topic', topic.value);
                if (sheet && sheet.value) params.set('sheet', sheet.value);
                if (hints && hints.checked) params.set('hints', '1');
                window.location.href = '/questions?' + params.toString();
            }, 1500);
        }
    } catch (e) {
        setTimeout(pollBulkStatus, 3000);
    }
}
