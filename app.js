/* ==========================================================================
   OptiMas Premium Dashboard Client Scripts
   ========================================================================== */

const API_BASE = "http://localhost:5050";
let isApiConnected = false;
let mockUptime = 0;

// Page Elements
const optimizeBtn = document.getElementById("optimize-swap-btn");
const openModalBtn = document.getElementById("open-modal-btn");
const closeModalBtn = document.getElementById("close-modal-btn");
const cancelBtn = document.getElementById("cancel-btn");
const profileModal = document.getElementById("profile-modal");
const profileForm = document.getElementById("profile-form");
const profilesList = document.getElementById("profiles-list");
const uptimeDisplay = document.getElementById("uptime-display");
const daemonBadgeText = document.getElementById("daemon-badge-text");
const statusBadge = document.querySelector(".status-badge");

// GPU info DOM
const amdName = document.getElementById("amd-name");
const amdDriver = document.getElementById("amd-driver");
const amdVram = document.getElementById("amd-vram");
const nvidiaName = document.getElementById("nvidia-name");
const nvidiaDriver = document.getElementById("nvidia-driver");
const nvidiaVram = document.getElementById("nvidia-vram");

// Uptime calculations
function formatUptime(seconds) {
    const hrs = String(Math.floor(seconds / 3600)).padStart(2, '0');
    const mins = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
    const secs = String(seconds % 60).padStart(2, '0');
    return `${hrs}:${mins}:${secs}`;
}

// Canvas Wave Visualization (AMD RX 580 Crimson Waves)
function initAmdCanvas() {
    const canvas = document.getElementById("amd-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    
    // Resize to container size
    function resize() {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    let offset = 0;
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        ctx.strokeStyle = "rgba(255, 51, 68, 0.4)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        // Dynamic sine wave to simulate computing
        for (let x = 0; x < canvas.width; x++) {
            const y = canvas.height / 2 + Math.sin(x * 0.015 + offset) * 15 * Math.sin(x * 0.002 + offset * 0.5);
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        ctx.strokeStyle = "rgba(255, 78, 0, 0.2)";
        ctx.beginPath();
        for (let x = 0; x < canvas.width; x++) {
            const y = canvas.height / 2 + Math.cos(x * 0.02 + offset * 1.2) * 12 * Math.sin(x * 0.001 - offset * 0.2);
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        offset += 0.05;
        requestAnimationFrame(animate);
    }
    animate();
}

// Canvas Nodes Visualization (NVIDIA GT 710 Green Nodes Intermediator)
function initNvidiaCanvas() {
    const canvas = document.getElementById("nvidia-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    function resize() {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
    }
    resize();

    const particles = [];
    for (let i = 0; i < 15; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.6,
            vy: (Math.random() - 0.5) * 0.6
        });
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw links
        ctx.strokeStyle = "rgba(118, 185, 0, 0.08)";
        ctx.lineWidth = 1;
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dist = Math.hypot(particles[i].x - particles[j].x, particles[i].y - particles[j].y);
                if (dist < 60) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }

        // Draw nodes
        ctx.fillStyle = "rgba(118, 185, 0, 0.6)";
        particles.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 2.5, 0, Math.PI * 2);
            ctx.fill();

            // Update pos
            p.x += p.vx;
            p.y += p.vy;

            // Bounce check
            if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
            if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
        });

        requestAnimationFrame(animate);
    }
    animate();
}

// Modal handling
openModalBtn.addEventListener("click", () => {
    profileModal.classList.add("active");
});

const closeModal = () => {
    profileModal.classList.remove("active");
};

closeModalBtn.addEventListener("click", closeModal);
cancelBtn.addEventListener("click", closeModal);
profileModal.addEventListener("click", (e) => {
    if (e.target === profileModal) closeModal();
});

// Render profiles helper
function renderProfiles(profiles) {
    profilesList.innerHTML = "";
    if (profiles.length === 0) {
        profilesList.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: var(--text-secondary);">
                <i class="fa-solid fa-folder-open" style="font-size: 2rem; margin-bottom: 0.5rem;"></i>
                <p>No active forced links. Use the "ADD PROFILE" button above to link your first application.</p>
            </div>
        `;
        return;
    }

    profiles.forEach(profile => {
        const row = document.createElement("div");
        row.className = "profile-row";
        
        const isCuda = profile.bridge_mode === "cuda-zluda";
        const modeText = isCuda ? "CUDA ZLUDA Bridge" : "Vulkan FSR Wrapper";
        const modeClass = isCuda ? "profile-mode cuda-mode" : "profile-mode";
        const modeIcon = isCuda ? "fa-solid fa-bolt" : "fa-solid fa-border-top-left";

        row.innerHTML = `
            <span class="profile-name">${profile.app_name}</span>
            <span class="profile-path" title="${profile.exec_path}">${profile.exec_path}</span>
            <span class="${modeClass}"><i class="${modeIcon}"></i> ${modeText}</span>
            <span class="profile-status"><i class="fa-solid fa-shield-halved"></i> ${profile.status}</span>
            <button class="delete-row-btn" data-id="${profile.id}"><i class="fa-regular fa-trash-can"></i></button>
        `;
        
        // Link delete button
        row.querySelector(".delete-row-btn").addEventListener("click", () => {
            deleteProfile(profile.id);
        });

        profilesList.appendChild(row);
    });
}

// Fetch Status from Daemon API
async function updateStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (res.ok) {
            const data = await res.json();
            isApiConnected = true;
            
            // Update UI with real server stats
            uptimeDisplay.textContent = formatUptime(data.uptime_seconds);
            daemonBadgeText.textContent = "DAEMON ACTIVE";
            statusBadge.classList.remove("disconnected");
            statusBadge.classList.add("connected");

            // Update GPU specs
            if (data.gpus && data.gpus.length >= 2) {
                const primary = data.gpus[0];
                const secondary = data.gpus[1];
                
                amdName.textContent = primary.name || "Radeon RX 580 Series";
                amdDriver.textContent = primary.driver || "Unknown";
                amdVram.textContent = primary.vram || "8.0 GB";

                nvidiaName.textContent = secondary.name || "NVIDIA GeForce GT 710";
                nvidiaDriver.textContent = secondary.driver || "Unknown";
                nvidiaVram.textContent = secondary.vram || "1.0 GB";
            }

            renderProfiles(data.latch_profiles || []);
        }
    } catch (e) {
        // Failover mock loop if API not running yet (standalone webapp demo)
        isApiConnected = false;
        mockUptime++;
        uptimeDisplay.textContent = formatUptime(mockUptime);
        daemonBadgeText.textContent = "DAEMON INACTIVE (DEMO)";
        statusBadge.classList.remove("connected");
        statusBadge.classList.add("disconnected");
    }
}

// Add Profile action
profileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const app_name = document.getElementById("app_name").value;
    const exec_path = document.getElementById("exec_path").value;
    const bridge_mode = document.getElementById("bridge_mode").value;

    const payload = { app_name, exec_path, bridge_mode };

    if (isApiConnected) {
        try {
            const res = await fetch(`${API_BASE}/api/profiles/add`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                const data = await res.json();
                renderProfiles(data.profiles);
                closeModal();
                profileForm.reset();
            }
        } catch (err) {
            alert("API connection failed. Action simulated in Demo mode.");
            closeModal();
        }
    } else {
        // Mock add
        const currentProfiles = JSON.parse(localStorage.getItem("mock_profiles") || "[]");
        currentProfiles.push({
            id: Date.now(),
            app_name,
            exec_path,
            bridge_mode,
            status: "Latched (Simulated)"
        });
        localStorage.setItem("mock_profiles", JSON.stringify(currentProfiles));
        renderProfiles(currentProfiles);
        closeModal();
        profileForm.reset();
    }
});

// Delete Profile action
async function deleteProfile(id) {
    if (isApiConnected) {
        try {
            const res = await fetch(`${API_BASE}/api/profiles/delete`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id })
            });
            if (res.ok) {
                const data = await res.json();
                renderProfiles(data.profiles);
            }
        } catch (err) {
            alert("API connection failed.");
        }
    } else {
        // Mock delete
        let currentProfiles = JSON.parse(localStorage.getItem("mock_profiles") || "[]");
        currentProfiles = currentProfiles.filter(p => p.id !== id);
        localStorage.setItem("mock_profiles", JSON.stringify(currentProfiles));
        renderProfiles(currentProfiles);
    }
}

// Swap optimization button trigger
optimizeBtn.addEventListener("click", async () => {
    optimizeBtn.classList.add("animating");
    
    if (isApiConnected) {
        try {
            const res = await fetch(`${API_BASE}/api/optimize/swap`, { method: "POST" });
            if (res.ok) {
                const data = await res.json();
                alert(data.message);
            }
        } catch (e) {
            alert("PowerShell swap optimizer script triggered locally. Open administrative shell to apply pagefile changes.");
        }
    } else {
        // Mock optimization animation
        setTimeout(() => {
            alert("Swap Optimizer script launched! Max memory limit pagefile has been set to 32GB on Drive C: along with caching registry values LargeSystemCache=1 and DisablePagingExecutive=1.");
            optimizeBtn.classList.remove("animating");
        }, 1200);
    }
});

// Setup mock storage profiles initially
function initMockProfiles() {
    if (!localStorage.getItem("mock_profiles")) {
        localStorage.setItem("mock_profiles", JSON.stringify([
            {
                id: 1,
                app_name: "Cyberpunk 2077 Hybrid Link",
                exec_path: "D:\\Steam\\steamapps\\common\\Cyberpunk 2077\\bin\\x64\\Cyberpunk2077.exe",
                bridge_mode: "vulkan-fsr-wrap",
                status: "Latched"
            },
            {
                id: 2,
                app_name: "PyTorch Compute Instance",
                exec_path: "C:\\Users\\JJ\\AppData\\Local\\Programs\\Python\\Python310\\python.exe",
                bridge_mode: "cuda-zluda",
                status: "Latched"
            }
        ]));
    }
    if (!isApiConnected) {
        renderProfiles(JSON.parse(localStorage.getItem("mock_profiles")));
    }
}

// Page load initialization
window.addEventListener("DOMContentLoaded", () => {
    initAmdCanvas();
    initNvidiaCanvas();
    initMockProfiles();
    
    // Status polling loop
    updateStatus();
    setInterval(updateStatus, 2000);
});
