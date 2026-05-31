window.addEventListener('DOMContentLoaded', () => {
    initAdminUI();
    setDefaultDate();
    loadBackups();
    loadCustomers();
    loadRecords();
});

function getAuthHeaders() {
    const token = sessionStorage.getItem('adminToken') || localStorage.getItem('adminToken');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return headers;
}

function initAdminUI() {
    document.getElementById('save-customer-button').addEventListener('click', saveCustomerMapping);
    document.getElementById('load-records-button').addEventListener('click', loadRecords);
    document.getElementById('logout-button').addEventListener('click', logout);
    document.getElementById('download-db-button').addEventListener('click', downloadDatabase);
    document.getElementById('create-backup-button').addEventListener('click', createLocalBackup);
    document.getElementById('refresh-backups-button').addEventListener('click', loadBackups);
    document.getElementById('customer-select').addEventListener('change', loadRecords);
}

async function downloadDatabase() {
    const token = sessionStorage.getItem('adminToken') || localStorage.getItem('adminToken');
    if (!token) {
        alert('Admin session not found. Please log in again.');
        return;
    }

    try {
        const response = await fetch('/api/export-db', {
            headers: { 'Authorization': 'Bearer ' + token }
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || `Download failed: ${response.status}`);
        }

        const blob = await response.blob();
        const contentDisposition = response.headers.get('content-disposition') || '';
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
        const filename = filenameMatch ? filenameMatch[1] : 'app.db';
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Failed to download database:', error);
        alert('Failed to download database. Please log in again and try once more.');
    }
}

async function createLocalBackup() {
    const messageNode = document.getElementById('backup-message');
    messageNode.textContent = 'Creating backup...';
    messageNode.className = 'info-box';

    try {
        const response = await fetch('/api/backups', {
            method: 'POST',
            headers: getAuthHeaders()
        });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || result.message || `Backup failed: ${response.status}`);
        }

        messageNode.textContent = `Backup created: ${result.backup.filename}`;
        messageNode.className = 'info-box success';
        loadBackups();
    } catch (error) {
        console.error('Failed to create backup:', error);
        messageNode.textContent = 'Failed to create backup. Please log in again and try once more.';
        messageNode.className = 'info-box error';
    }
}

async function loadBackups() {
    const tableBody = document.querySelector('#backups-table tbody');
    const settingsNode = document.getElementById('backup-settings');

    if (!tableBody || !settingsNode) return;

    tableBody.innerHTML = '<tr><td colspan="4">Loading backups...</td></tr>';

    try {
        const response = await fetch('/api/backups', { headers: getAuthHeaders() });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || `Failed to load backups: ${response.status}`);
        }

        const result = await response.json();
        const backups = Array.isArray(result.backups) ? result.backups : [];
        settingsNode.textContent = `Local folder: ${result.backup_dir} | Auto backup: ${formatInterval(result.interval_seconds)} | Keep latest: ${result.retention_count}`;
        tableBody.innerHTML = '';

        if (backups.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4">No backups created yet.</td></tr>';
            return;
        }

        backups.forEach(backup => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${backup.filename}</td>
                <td>${new Date(backup.created_at).toLocaleString()}</td>
                <td>${formatBytes(backup.size_bytes)}</td>
                <td><button class="action-btn download-backup-button" data-filename="${backup.filename}">Download</button></td>
            `;
            tableBody.appendChild(row);
        });

        document.querySelectorAll('.download-backup-button').forEach(button => {
            button.addEventListener('click', () => downloadBackup(button.dataset.filename));
        });
    } catch (error) {
        console.error('Failed to load backups:', error);
        tableBody.innerHTML = '<tr><td colspan="4">Error loading backups.</td></tr>';
        settingsNode.textContent = '';
    }
}

async function downloadBackup(filename) {
    const token = sessionStorage.getItem('adminToken') || localStorage.getItem('adminToken');
    if (!token) {
        alert('Admin session not found. Please log in again.');
        return;
    }

    try {
        const response = await fetch(`/api/backups/${encodeURIComponent(filename)}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || `Download failed: ${response.status}`);
        }

        const blob = await response.blob();
        triggerBlobDownload(blob, filename);
    } catch (error) {
        console.error('Failed to download backup:', error);
        alert('Failed to download backup. Please log in again and try once more.');
    }
}

function triggerBlobDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

function formatBytes(bytes) {
    const value = Number(bytes);
    if (!Number.isFinite(value) || value < 0) return '--';
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatInterval(seconds) {
    const value = Number(seconds);
    if (!Number.isFinite(value) || value <= 0) return 'disabled';
    if (value % 86400 === 0) return `${value / 86400} day(s)`;
    if (value % 3600 === 0) return `${value / 3600} hour(s)`;
    return `${value} second(s)`;
}

function setDefaultDate() {
    const dateInput = document.getElementById('record-date');
    const today = new Date().toISOString().split('T')[0];
    dateInput.value = today;
}

async function saveCustomerMapping() {
    const deviceId = document.getElementById('device-id-input').value.trim();
    const customerName = document.getElementById('customer-name-input').value.trim();
    const ptName = document.getElementById('pt-name-input').value.trim();
    const messageNode = document.getElementById('customer-message');

    if (!deviceId || !customerName || !ptName) {
        messageNode.textContent = 'Please fill in all fields.';
        messageNode.className = 'info-box error';
        return;
    }

    try {
        const response = await fetch('/api/customers', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                device_id: deviceId,
                customer_name: customerName,
                pt_name: ptName,
                phone_number: document.getElementById('phone-input')?.value?.trim() || null,
                gender: document.getElementById('gender-select')?.value || null,
                weight_kg: parseFloat(document.getElementById('weight-input')?.value) || null,
                birthday: document.getElementById('birthday-input')?.value || null
            })
        });
        const result = await response.json();

        if (response.ok) {
            messageNode.textContent = result.message;
            messageNode.className = 'info-box success';
            document.getElementById('customer-form').reset();
            loadCustomers();
        } else {
            messageNode.textContent = result.message || 'Unable to save.';
            messageNode.className = 'info-box error';
        }
    } catch (error) {
        console.error(error);
        messageNode.textContent = 'Failed to save mapping.';
        messageNode.className = 'info-box error';
    }
}

async function loadCustomers() {
    try {
        const response = await fetch('/api/customers', { headers: getAuthHeaders() });
        if (!response.ok) {
            throw new Error(`Failed to load customers: ${response.status}`);
        }
        const customers = await response.json();

        const tableBody = document.querySelector('#customers-table tbody');
        const select = document.getElementById('customer-select');
        tableBody.innerHTML = '';
        select.innerHTML = '';
        customersById.clear();

        customers.forEach(customer => {
            customersById.set(String(customer.id), customer);
            const row = document.createElement('tr');
            row.dataset.customerId = customer.id;
            row.innerHTML = `
                <td>${customer.device_id}</td>
                <td>${customer.customer}</td>
                <td>${customer.phone_number || ''}</td>
                <td>${customer.gender || ''}</td>
                <td>${customer.weight_kg != null ? customer.weight_kg : ''}</td>
                <td>${customer.birthday || ''}</td>
                <td>${customer.pt_name}</td>
                <td>${new Date(customer.updated_at).toLocaleString()}</td>
                <td><button class="action-btn" data-customer-id="${customer.id}">Show Graph</button></td>
            `;
            tableBody.appendChild(row);

            // placeholder expand row (hidden initially)
            const expandRow = document.createElement('tr');
            expandRow.className = 'expand-row';
            expandRow.style.display = 'none';
            expandRow.innerHTML = `<td colspan="9"><canvas id="chart-canvas-${customer.id}" class="chart-canvas"></canvas></td>`;
            tableBody.appendChild(expandRow);

            const option = document.createElement('option');
            option.value = customer.id;
            option.textContent = `${customer.customer} (${customer.device_id})`;
            select.appendChild(option);
        });

        if (customers.length === 0) {
            select.innerHTML = '<option value="">No customers registered</option>';
        }

        // attach event listeners for graph buttons
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const cid = e.currentTarget.dataset.customerId;
                toggleGraphRow(cid);
            });
        });

        loadRecords();
    } catch (error) {
        console.error('Failed to load customers:', error);
    }
}

let recordChart = null;
const customersById = new Map();

async function loadRecords() {
    const select = document.getElementById('customer-select');
    const customerId = select.value;
    const date = document.getElementById('record-date').value;
    const tableBody = document.querySelector('#records-table tbody');
    tableBody.innerHTML = '';

    if (!customerId) {
        tableBody.innerHTML = '<tr><td colspan="4">Select a customer to view workout data.</td></tr>';
        renderWorkoutSummary([], null);
        return;
    }

    try {
        const params = new URLSearchParams({ customer_id: customerId, date });
        const response = await fetch(`/api/records?${params.toString()}`, { headers: getAuthHeaders() });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || `Failed to load records: ${response.status}`);
        }
        const records = await response.json();

        if (!Array.isArray(records) || records.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4">No records for this date.</td></tr>';
            renderWorkoutSummary([], customersById.get(String(customerId)));
            return;
        }

        records.forEach(record => {
            const timeLabel = new Date(record.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${timeLabel}</td>
                <td>${record.heart_rate} BPM</td>
                <td>${record.protocol}</td>
                <td>${record.device_id}</td>
            `;
            tableBody.appendChild(row);
        });

        renderWorkoutSummary(records, customersById.get(String(customerId)));
    } catch (error) {
        console.error('Failed to load records:', error);
        tableBody.innerHTML = '<tr><td colspan="4">Error loading records.</td></tr>';
        renderWorkoutSummary([], customersById.get(String(customerId)));
    }
}

function renderWorkoutSummary(records, customer) {
    const durationEl = document.getElementById('summary-duration');
    const caloriesEl = document.getElementById('summary-calories');
    const peakEl = document.getElementById('summary-peak');
    const averageEl = document.getElementById('summary-average');
    const countEl = document.getElementById('summary-count');

    if (!records || records.length === 0) {
        durationEl.textContent = '--:--';
        caloriesEl.textContent = '--';
        peakEl.textContent = '--';
        averageEl.textContent = '--';
        countEl.textContent = '0';
        return;
    }

    const sorted = [...records].sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    const durationSeconds = Math.max(0, (sorted[sorted.length - 1].timestamp || 0) - (sorted[0].timestamp || 0));
    const averageHeartRate = Math.round(records.reduce((sum, record) => sum + (record.heart_rate || 0), 0) / records.length);
    const peakHeartRate = Math.max(...records.map(record => record.heart_rate || 0));
    const calories = calculateWorkoutCalories(sorted, customer);

    durationEl.textContent = `${String(Math.floor(durationSeconds / 60)).padStart(2, '0')}:${String(durationSeconds % 60).padStart(2, '0')}`;
    caloriesEl.textContent = calories == null ? '--' : calories.toString();
    peakEl.textContent = `${peakHeartRate} BPM`;
    averageEl.textContent = `${averageHeartRate} BPM`;
    countEl.textContent = records.length.toString();
}

function calculateWorkoutCalories(sortedRecords, customer) {
    const weightKg = Number(customer?.weight_kg);
    const summaryDate = document.getElementById('record-date')?.value;
    const age = calculateAge(customer?.birthday, summaryDate);
    if (!Number.isFinite(weightKg) || weightKg <= 0 || age == null) return null;

    const weightLbs = weightKg * 2.20462;
    const isFemale = String(customer?.gender || '').toLowerCase() === 'female';

    const totalCalories = sortedRecords.reduce((total, record, index) => {
        const heartRate = Number(record.heart_rate) || 0;
        if (index === sortedRecords.length - 1 || heartRate <= 90) return total;

        const seconds = Math.max(0, (sortedRecords[index + 1].timestamp || 0) - (record.timestamp || 0));
        const caloriesPerMinute = isFemale
            ? (-20.4022 + (0.4472 * heartRate) - (0.1263 * weightLbs) + (0.074 * age)) / 4.184
            : (-55.0969 + (0.6309 * heartRate) + (0.1988 * weightLbs) + (0.2017 * age)) / 4.184;

        return total + (Math.max(0, caloriesPerMinute) * (seconds / 60));
    }, 0);

    return Math.round(totalCalories);
}

function calculateAge(birthday, asOfDateValue) {
    if (!birthday) return null;

    const birthDate = new Date(`${birthday}T00:00:00`);
    if (Number.isNaN(birthDate.getTime())) return null;

    const asOfDate = asOfDateValue ? new Date(`${asOfDateValue}T00:00:00`) : new Date();
    if (Number.isNaN(asOfDate.getTime())) return null;

    let age = asOfDate.getFullYear() - birthDate.getFullYear();
    const hasHadBirthdayThisYear =
        asOfDate.getMonth() > birthDate.getMonth() ||
        (asOfDate.getMonth() === birthDate.getMonth() && asOfDate.getDate() >= birthDate.getDate());

    if (!hasHadBirthdayThisYear) age -= 1;
    return age >= 0 ? age : null;
}

function getHeartRateColor(heartRate) {
    if (heartRate < 70) return '#bdc3c7';
    if (heartRate < 90) return '#95a5a6';
    if (heartRate < 100) return '#e67e22';
    if (heartRate < 125) return '#ee5859';
    return '#c0392b';
}

async function renderCustomerChart(customerId) {
    const canvasId = `chart-canvas-${customerId}`;
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // try to fetch records for this customer (no date to get all recent)
    let records = [];
    try {
        const response = await fetch(`/api/records?customer_id=${encodeURIComponent(customerId)}`, { headers: getAuthHeaders() });
        if (response.ok) records = await response.json();
    } catch (e) {
        console.warn('Failed to fetch records for chart', e);
    }

    if (!records || records.length === 0) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#ffffff';
        ctx.font = '16px sans-serif';
        ctx.fillText('No records available to display.', 10, 30);
        return;
    }

    records.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    const labels = records.map(record => new Date((record.timestamp || 0) * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    const values = records.map(record => record.heart_rate || 0);
    const backgroundColors = values.map(getHeartRateColor);

    if (canvas._chartInstance) {
        try { canvas._chartInstance.destroy(); } catch (e) {}
        canvas._chartInstance = null;
    }

    const ctx = canvas.getContext('2d');
    canvas._chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Heart Rate (BPM)',
                data: values,
                backgroundColor: backgroundColors,
                borderColor: backgroundColors,
                borderWidth: 1,
                maxBarThickness: 24
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: context => `${context.parsed.y} BPM`
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Time' },
                    ticks: { color: '#ffffff' }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'BPM' },
                    ticks: { color: '#ffffff' }
                }
            }
        }
    });
}

function logout() {
    const token = sessionStorage.getItem('adminToken') || localStorage.getItem('adminToken');
    // call logout API to invalidate token server-side
    if (token) {
        fetch('/api/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
            body: JSON.stringify({ token })
        }).catch(() => {});
    }
    sessionStorage.removeItem('adminToken');
    localStorage.removeItem('adminToken');
    window.location.href = '/';
}

async function toggleGraphRow(customerId) {
    const tableBody = document.querySelector('#customers-table tbody');
    // find the main row and the expansion row (next sibling)
    const mainRow = tableBody.querySelector(`tr[data-customer-id="${customerId}"]`);
    if (!mainRow) return;
    const expandRow = mainRow.nextElementSibling;
    if (!expandRow || !expandRow.classList.contains('expand-row')) return;

    if (expandRow.style.display === 'none' || !expandRow.style.display) {
        // show and render chart
        expandRow.style.display = '';
        await renderCustomerChart(customerId);
        // scroll into view
        expandRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } else {
        // hide
        expandRow.style.display = 'none';
    }
}
