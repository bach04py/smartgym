window.addEventListener('DOMContentLoaded', () => {
    initAdminUI();
    setDefaultDate();
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
            method: 'GET',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            const message = await response.text();
            throw new Error(message || 'Failed to download database');
        }

        const blob = await response.blob();
        const disposition = response.headers.get('Content-Disposition');
        let filename = 'app.db';
        if (disposition) {
            const match = /filename="?([^";]+)"?/.exec(disposition);
            if (match) filename = match[1];
        }

        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Download failed:', error);
        alert('Database download failed. Please check your admin session and try again.');
    }
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
                age: parseInt(document.getElementById('age-input')?.value) || null
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
        const customers = await response.json();

        const tableBody = document.querySelector('#customers-table tbody');
        const select = document.getElementById('customer-select');
        tableBody.innerHTML = '';
        select.innerHTML = '';

        customers.forEach(customer => {
            const row = document.createElement('tr');
            row.dataset.customerId = customer.id;
            row.innerHTML = `
                <td>${customer.device_id}</td>
                <td>${customer.customer}</td>
                <td>${customer.phone_number || ''}</td>
                <td>${customer.gender || ''}</td>
                <td>${customer.weight_kg != null ? customer.weight_kg : ''}</td>
                <td>${customer.age != null ? customer.age : ''}</td>
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

async function loadRecords() {
    const select = document.getElementById('customer-select');
    const customerId = select.value;
    const date = document.getElementById('record-date').value;
    const tableBody = document.querySelector('#records-table tbody');
    tableBody.innerHTML = '';

    if (!customerId) {
        tableBody.innerHTML = '<tr><td colspan="4">Select a customer to view workout data.</td></tr>';
        renderRecordBarChart([]);
        return;
    }

    try {
        const params = new URLSearchParams({ customer_id: customerId, date });
        const response = await fetch(`/api/records?${params.toString()}`, { headers: getAuthHeaders() });
        const records = await response.json();

        if (records.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4">No records for this date.</td></tr>';
            renderRecordBarChart([]);
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

        renderRecordBarChart(records);
    } catch (error) {
        console.error('Failed to load records:', error);
        tableBody.innerHTML = '<tr><td colspan="4">Error loading records.</td></tr>';
        renderRecordBarChart([]);
    }
}

function getHeartRateColor(heartRate) {
    if (heartRate >= 170) return '#e74c3c';
    if (heartRate >= 150) return '#f39c12';
    if (heartRate >= 130) return '#f1c40f';
    if (heartRate >= 110) return '#2ecc71';
    return '#3498db';
}

function renderRecordBarChart(records) {
    const canvas = document.getElementById('record-bar-chart');
    if (!canvas) return;

    if (recordChart) {
        recordChart.destroy();
        recordChart = null;
    }

    const ctx = canvas.getContext('2d');
    if (!records || records.length === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#ffffff';
        ctx.font = '16px sans-serif';
        ctx.fillText('Load a record to view the workout bar chart.', 10, 30);
        return;
    }

    const labels = records.map(record => new Date(record.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    const values = records.map(record => record.heart_rate);
    const backgroundColors = values.map(getHeartRateColor);

    recordChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Heart Rate (BPM)',
                data: values,
                backgroundColor: backgroundColors,
                borderColor: backgroundColors,
                borderWidth: 1,
                hoverBackgroundColor: backgroundColors,
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

    // fallback: if no records returned, show message inside canvas area
    if (!records || records.length === 0) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#ffffff';
        ctx.font = '16px sans-serif';
        ctx.fillText('No records available to display.', 10, 30);
        return;
    }

    // group records by day (or use timestamp order)
    records.sort((a,b)=> (a.timestamp||0)-(b.timestamp||0));
    const labels = records.map(r => new Date((r.timestamp||0)*1000).toLocaleString());
    const hrData = records.map(r => r.heart_rate || null);

    // destroy existing chart instance if present
    if (canvas._chartInstance) {
        try { canvas._chartInstance.destroy(); } catch(e){}
        canvas._chartInstance = null;
    }

    const ctx = canvas.getContext('2d');
    canvas._chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Heart Rate (BPM)',
                data: hrData,
                borderColor: '#ff3333',
                backgroundColor: 'rgba(255,51,51,0.12)',
                tension: 0.2,
                pointRadius: 3,
                fill: true,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: true, title: { display: false } },
                y: { display: true, title: { display: true, text: 'BPM' }, suggestedMin: 40 }
            },
            plugins: {
                legend: { display: true }
            }
        }
    });
}
