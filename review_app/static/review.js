/* QuestionReview client-side JS */

// Bulk generation
async function bulkGenerate() {
    const ids = Array.from(selected);
    if (!ids.length) return;

    const btn = document.getElementById('bulk-gen-btn');
    btn.disabled = true;
    btn.textContent = 'Starting...';

    try {
        const res = await fetch('/api/bulk-generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item_ids: ids})
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
        document.getElementById('bulk-progress-bar').style.width = pct + '%';
        document.getElementById('bulk-progress-text').textContent =
            `${data.completed} / ${data.total}` +
            (data.errors.length ? ` (${data.errors.length} errors)` : '');
        document.getElementById('bulk-indicator-text').textContent =
            `Generating ${data.completed}/${data.total}...`;

        if (data.running) {
            setTimeout(pollBulkStatus, 2000);
        } else {
            // Done — update the table data
            document.getElementById('bulk-indicator-text').textContent = 'Done!';
            setTimeout(() => {
                hideBulkProgress();
                // Refresh page to get updated state
                window.location.reload();
            }, 1500);
        }
    } catch (e) {
        setTimeout(pollBulkStatus, 3000);
    }
}
