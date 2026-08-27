document.addEventListener('DOMContentLoaded', function () {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('foodImage');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const uploadForm = document.getElementById('uploadForm');
    const previewSection = document.getElementById('previewSection');
    const imagePreview = document.getElementById('imagePreview');
    const loading = document.getElementById('loading');
    const browseBtn = document.getElementById('browseBtn');
    const cameraBtn = document.getElementById('cameraBtn');

    // Create Toast Element
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="#EF4444" style="width: 20px; height: 20px; flex-shrink: 0;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
        <span id="toastMessage"></span>
    `;
    document.body.appendChild(toast);

    let toastTimeout = null;
    function showToast(message) {
        const toastMsg = document.getElementById('toastMessage');
        toastMsg.textContent = message;
        toast.classList.add('show');
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 5000);
    }

    // Click on browse button
    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.removeAttribute('capture');
            fileInput.click();
        });
    }

    // WebRTC Camera Elements
    const cameraModal = document.getElementById('cameraModal');
    const cameraVideo = document.getElementById('cameraVideo');
    const cameraCanvas = document.getElementById('cameraCanvas');
    const snapBtn = document.getElementById('snapBtn');
    const closeCameraBtn = document.getElementById('closeCameraBtn');
    let videoStream = null;

    if (cameraBtn) {
        cameraBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
            
            if (isMobile) {
                fileInput.setAttribute('capture', 'environment');
                fileInput.click();
            } else {
                try {
                    videoStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
                    cameraVideo.srcObject = videoStream;
                    cameraModal.style.display = 'flex';
                } catch (err) {
                    console.error("Camera access denied or unavailable", err);
                    showToast("Could not access your camera. Make sure your browser has camera permission.");
                }
            }
        });
    }

    if (closeCameraBtn) {
        closeCameraBtn.addEventListener('click', () => {
            cameraModal.style.display = 'none';
            if (videoStream) {
                videoStream.getTracks().forEach(track => track.stop());
                videoStream = null;
            }
        });
    }

    if (snapBtn) {
        snapBtn.addEventListener('click', () => {
            const context = cameraCanvas.getContext('2d');
            cameraCanvas.width = cameraVideo.videoWidth || 640;
            cameraCanvas.height = cameraVideo.videoHeight || 480;
            context.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
            
            cameraCanvas.toBlob((blob) => {
                const file = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
                
                cameraModal.style.display = 'none';
                if (videoStream) {
                    videoStream.getTracks().forEach(track => track.stop());
                    videoStream = null;
                }
                
                const event = new Event('change');
                fileInput.dispatchEvent(event);
            }, 'image/jpeg', 0.9);
        });
    }

    // Default upload area click triggers normal file browser
    if (uploadArea) {
        uploadArea.addEventListener('click', () => {
            fileInput.removeAttribute('capture');
            fileInput.click();
        });
    }

    // Handle file selection
    if (fileInput) {
        fileInput.addEventListener('change', function () {
            if (this.files && this.files[0]) {
                const file = this.files[0];
                const reader = new FileReader();
                reader.onload = function (e) {
                    imagePreview.src = e.target.result;
                    previewSection.style.display = 'block';
                    analyzeBtn.disabled = false;
                    previewSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // Drag and drop functionality
    if (uploadArea) {
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');

            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                fileInput.files = e.dataTransfer.files;
                const event = new Event('change');
                fileInput.dispatchEvent(event);
            }
        });
    }

    // Dynamic loading messages
    const loadingSteps = [
        "Analyzing food visual features...",
        "Identifying culinary dishes & portion sizes...",
        "Computing clinical macronutrients & dietitian advice..."
    ];
    let stepInterval = null;

    // Form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', function (e) {
            e.preventDefault();

            if (!fileInput.files[0]) {
                showToast('Please select or capture a food photo first.');
                return;
            }

            loading.style.display = 'block';
            analyzeBtn.disabled = true;

            const loadingText = loading.querySelector('p');
            let stepIdx = 0;
            if (loadingText) {
                loadingText.textContent = loadingSteps[0];
                stepInterval = setInterval(() => {
                    stepIdx = (stepIdx + 1) % loadingSteps.length;
                    loadingText.textContent = loadingSteps[stepIdx];
                }, 1800);
            }

            const formData = new FormData(uploadForm);

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
                .then(async response => {
                    if (stepInterval) clearInterval(stepInterval);
                    
                    if (!response.ok) {
                        let errorMessage = 'Unable to analyze image. Please try again.';
                        try {
                            const errData = await response.json();
                            if (errData.error) {
                                errorMessage = errData.error;
                            }
                        } catch (e) {
                            // Ignore json parse error
                        }
                        throw new Error(errorMessage);
                    }
                    return response.text();
                })
                .then(html => {
                    document.open();
                    document.write(html);
                    document.close();
                })
                .catch(error => {
                    if (stepInterval) clearInterval(stepInterval);
                    console.error('Error:', error);
                    showToast(error.message || 'Unable to process image. Please try again.');
                    loading.style.display = 'none';
                    analyzeBtn.disabled = false;
                });
        });
    }
});

// Clear image function
function clearImage() {
    const fileInput = document.getElementById('foodImage');
    const previewSection = document.getElementById('previewSection');
    const analyzeBtn = document.getElementById('analyzeBtn');

    if (fileInput) fileInput.value = '';
    if (previewSection) previewSection.style.display = 'none';
    if (analyzeBtn) analyzeBtn.disabled = true;
}