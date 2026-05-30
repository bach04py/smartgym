// Dynamically construct WebSocket URL based on current page location
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const host = window.location.host;  // Includes both IP and port
const wsUrl = `${protocol}//${host}/ws`;

console.log(`Connecting to WebSocket: ${wsUrl}`);

const ws = new WebSocket(wsUrl);

let reconnectAttempts = 0;
const maxReconnectAttempts = 10;
const reconnectDelay = 3000;

window.addEventListener('DOMContentLoaded', () => {
    setupLoginModal();
});

function setupLoginModal() {
    const loginBtn = document.getElementById('login-button');
    const modal = document.getElementById('login-modal');
    const modalClose = document.getElementById('modal-close');
    const loginForm = document.getElementById('login-form');

    if (!loginBtn || !modal || !loginForm) return;

    loginBtn.addEventListener('click', () => {
        modal.style.display = 'block';
    });

    modalClose.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = document.getElementById('password-input').value;
        const msg = document.getElementById('login-message');
        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            const data = await res.json();
            if (res.ok && data.token) {
                const remember = document.getElementById('remember-checkbox')?.checked;
                if (remember) localStorage.setItem('adminToken', data.token);
                else sessionStorage.setItem('adminToken', data.token);
                window.location.href = '/admin?token=' + data.token;
            } else {
                msg.textContent = data.message || 'Login failed';
                msg.className = 'info-box error';
            }
        } catch (err) {
            console.error(err);
            msg.textContent = 'Connection error';
            msg.className = 'info-box error';
        }
    });
}

function initAdminUI() {
    document.getElementById('save-customer-button').addEventListener('click', saveCustomerMapping);
    document.getElementById('load-records-button').addEventListener('click', loadRecords);
    document.getElementById('customer-select').addEventListener('change', loadRecords);
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
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                device_id: deviceId,
                customer_name: customerName,
                pt_name: ptName
            })
        });
        const result = await response.json();

        if (response.ok) {
            messageNode.textContent = result.message;
            messageNode.className = 'info-box success';
            loadCustomers();
        } else {
            messageNode.textContent = result.message || 'Unable to save customer mapping.';
            messageNode.className = 'info-box error';
        }
    } catch (error) {
        console.error(error);
        messageNode.textContent = 'Failed to save mapping. Please try again.';
        messageNode.className = 'info-box error';
    }
}

async function loadCustomers() {
    try {
        const response = await fetch('/api/customers');
        const customers = await response.json();

        const tableBody = document.querySelector('#customers-table tbody');
        const select = document.getElementById('customer-select');
        tableBody.innerHTML = '';
        select.innerHTML = '';

        customers.forEach(customer => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${customer.device_id}</td>
                <td>${customer.customer}</td>
                <td>${customer.pt_name}</td>
                <td>${new Date(customer.updated_at).toLocaleString()}</td>
            `;
            tableBody.appendChild(row);

            const option = document.createElement('option');
            option.value = customer.id;
            option.textContent = `${customer.customer} (${customer.device_id})`;
            select.appendChild(option);
        });

        if (customers.length === 0) {
            select.innerHTML = '<option value="">No customers registered</option>';
        }

        loadRecords();
    } catch (error) {
        console.error('Failed to load customers:', error);
    }
}

async function loadRecords() {
    const select = document.getElementById('customer-select');
    const customerId = select.value;
    const date = document.getElementById('record-date').value;
    const tableBody = document.querySelector('#records-table tbody');
    tableBody.innerHTML = '';

    if (!customerId) {
        tableBody.innerHTML = '<tr><td colspan="4">Please register a customer and select one to view workout data.</td></tr>';
        return;
    }

    try {
        const params = new URLSearchParams({ customer_id: customerId, date });
        const response = await fetch(`/api/records?${params.toString()}`);
        const records = await response.json();

        if (records.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4">No records for this customer on the selected date.</td></tr>';
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
    } catch (error) {
        console.error('Failed to load records:', error);
        tableBody.innerHTML = '<tr><td colspan="4">Error loading records. Refresh the page and try again.</td></tr>';
    }
}

function reconnectWebSocket() {
    if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        console.log(`Reconnect attempt ${reconnectAttempts}/${maxReconnectAttempts}...`);
        setTimeout(() => {
            location.reload();
        }, reconnectDelay);
    } else {
        console.error("Max reconnection attempts reached");
        document.getElementById("error-message").style.display = "block";
        document.getElementById("error-text").innerText = 
            "Error: Unable to reconnect to server. Check if server is running.";
    }
}

ws.onopen = () => {
    console.log("✓ WebSocket Connected");
    reconnectAttempts = 0;
    updateConnectionUI(true);
}

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    console.log(`Received ${data.total_devices} device(s):`, data);
    
    // Update global status
    updateGlobalStatus(data);
    
    // Update device cards
    updateDeviceCards(data.devices || []);
    
    // Update connection status
    updateConnectionUI(data.connection_status);
    
    // Handle errors
    if (data.last_error) {
        document.getElementById("error-message").style.display = "block";
        document.getElementById("error-text").innerText = 
            `Error: ${data.last_error}`;
    } else {
        document.getElementById("error-message").style.display = "none";
    }
}

ws.onerror = (error) => {
    console.error("✗ WebSocket Error:", error);
    updateConnectionUI(false);
    document.getElementById("error-message").style.display = "block";
    document.getElementById("error-text").innerText = 
        "Error: WebSocket connection failed";
}

ws.onclose = () => {
    console.log("✗ WebSocket Disconnected - attempting to reconnect");
    updateConnectionUI(false);
    document.getElementById("error-message").style.display = "block";
    document.getElementById("error-text").innerText = 
        "Error: Connection lost - reconnecting...";
    reconnectWebSocket();
}

function updateGlobalStatus(data) {
    document.getElementById("total-devices").innerText = 
        `Devices: ${data.total_devices}`;
    document.getElementById("stats").innerText = 
        `Messages: ${data.total_messages} | Errors: ${data.error_count}`;
}

function updateDeviceCards(devices) {
    const grid = document.getElementById("devices-grid");
    
    if (devices.length === 0) {
        if (!document.getElementById("empty-state")) {
            grid.innerHTML = `
                <div id="empty-state" class="empty-state">
                    <div class="empty-state-icon">⌛</div>
                    <div>Waiting for devices...</div>
                </div>
            `;
        }
        return;
    }
    
    const emptyState = document.getElementById("empty-state");
    if (emptyState) {
        emptyState.remove();
    }
    
    devices.forEach(device => {
        const deviceId = device.device_id;
        let card = document.getElementById(`device-card-${deviceId}`);
        
        if (!card) {
            card = document.createElement("div");
            card.id = `device-card-${deviceId}`;
            card.className = "device-card";
            grid.appendChild(card);
        }
        
        let timeSince = "N/A";
        if (device.received_at) {
            const receivedTime = new Date(device.received_at);
            const now = new Date();
            const diffSeconds = Math.round((now - receivedTime) / 1000);
            
            if (diffSeconds < 60) {
                timeSince = `${diffSeconds}s ago`;
            } else {
                timeSince = `${Math.round(diffSeconds / 60)}m ago`;
            }
        }
        
        const protocol = device.protocol || '-';
        card.innerHTML = `
            <div class="device-id">Device #${deviceId} <span class="protocol-badge">${protocol}</span></div>
            <div class="device-heart-rate">${device.heart_rate}</div>
            <div class="device-bpm">BPM</div>
            <div class="device-stats">
                <div class="stat-item">
                    <span class="stat-label">Beat Count</span>
                    <span class="stat-value">${device.beat_count || '-'}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Last Update</span>
                    <span class="stat-value">${timeSince}</span>
                </div>
            </div>
            <div class="device-status online">
                ✓ ACTIVE
            </div>
        `;
        
        card.classList.add("connected");

        const hr = Number(device.heart_rate);
        const zoneClasses = [
            'hr-zone-low',
            'hr-zone-normal',
            'hr-zone-high',
            'hr-zone-very-high'
        ];
        let zoneClass = null;
        if (!isNaN(hr)) {
            if (hr < 60) zoneClass = 'hr-zone-low';
            else if (hr < 101) zoneClass = 'hr-zone-normal';
            else if (hr < 141) zoneClass = 'hr-zone-high';
            else zoneClass = 'hr-zone-very-high';
        }
        zoneClasses.forEach(c => card.classList.remove(c));
        if (zoneClass) card.classList.add(zoneClass);
    });
    
    const deviceIds = new Set(devices.map(d => String(d.device_id)));
    const existingCards = grid.querySelectorAll(".device-card");
    
    existingCards.forEach(card => {
        const match = card.id.match(/device-card-(.+)/);
        if (match) {
            const cardDeviceId = match[1];
            if (!deviceIds.has(String(cardDeviceId))) {
                card.style.opacity = "0.5";
                const statusDiv = card.querySelector(".device-status");
                if (statusDiv) {
                    statusDiv.className = "device-status offline";
                    statusDiv.innerText = "✗ OFFLINE";
                }
            }
        }
    });
}

function updateConnectionUI(connected) {
    const indicator = document.getElementById("connection-indicator");
    if (connected) {
        indicator.classList.remove("disconnected");
        indicator.classList.add("connected");
        indicator.innerText = "● CONNECTED";
    } else {
        indicator.classList.remove("connected");
        indicator.classList.add("disconnected");
        indicator.innerText = "● DISCONNECTED";
    }
}

setInterval(async () => {
    try {
        const response = await fetch("/api/status");
        const status = await response.json();
        document.getElementById("stats").innerText = 
            `Messages: ${status.total_messages} | Errors: ${status.error_count}`;
        
    } catch (error) {
        console.error("Failed to fetch status:", error);
    }
}, 5000);
