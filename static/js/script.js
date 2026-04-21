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

    // Click on browse button
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.removeAttribute('capture');
        fileInput.click();
    });

    // WebRTC Elements
    const cameraModal = document.getElementById('cameraModal');
    const cameraVideo = document.getElementById('cameraVideo');
    const cameraCanvas = document.getElementById('cameraCanvas');
    const snapBtn = document.getElementById('snapBtn');
    const closeCameraBtn = document.getElementById('closeCameraBtn');
    let videoStream = null;

    // Click on camera button
    cameraBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        
        // If mobile, use native camera app. Else, use WebRTC popup for laptops
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        if (isMobile) {
            fileInput.setAttribute('capture', 'environment');
            fileInput.click();
        } else {
            try {
                videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
                cameraVideo.srcObject = videoStream;
                cameraModal.style.display = 'flex';
            } catch (err) {
                console.error("Camera access denied or unavailable", err);
                alert("Could not access your camera. Make sure your browser has permission.");
            }
        }
    });

    closeCameraBtn.addEventListener('click', () => {
        cameraModal.style.display = 'none';
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
        }
    });

    snapBtn.addEventListener('click', () => {
        const context = cameraCanvas.getContext('2d');
        cameraCanvas.width = cameraVideo.videoWidth;
        cameraCanvas.height = cameraVideo.videoHeight;
        context.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
        
        // Convert canvas image to Blob to simulate file upload
        cameraCanvas.toBlob((blob) => {
            const file = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
            
            // Close modal and stop stream
            cameraModal.style.display = 'none';
            if (videoStream) {
                videoStream.getTracks().forEach(track => track.stop());
            }
            
            // Trigger standard change event for preview
            const event = new Event('change');
            fileInput.dispatchEvent(event);
        }, 'image/jpeg', 0.9);
    });

    // Default upload area click triggers normal file browser
    uploadArea.addEventListener('click', () => {
        fileInput.removeAttribute('capture');
        fileInput.click();
    });

    // Handle file selection
    fileInput.addEventListener('change', function (e) {
        if (this.files && this.files[0]) {
            const file = this.files[0];

            // Show preview
            const reader = new FileReader();
            reader.onload = function (e) {
                imagePreview.src = e.target.result;
                previewSection.style.display = 'block';
                analyzeBtn.disabled = false;
            }
            reader.readAsDataURL(file);
        }
    });

    // Drag and drop functionality
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.background = '#f0f0f0';
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.background = '';
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.background = '';

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            fileInput.files = e.dataTransfer.files;
            const event = new Event('change');
            fileInput.dispatchEvent(event);
        }
    });

    // Form submission
    uploadForm.addEventListener('submit', function (e) {
        e.preventDefault();

        if (!fileInput.files[0]) return;

        loading.style.display = 'block';
        analyzeBtn.disabled = true;

        const formData = new FormData(uploadForm);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
            .then(async response => {
                if (!response.ok) {
                    let errorMessage = 'Network response was not ok';
                    try {
                        const errData = await response.json();
                        if (errData.error) {
                            errorMessage = errData.error;
                        }
                    } catch (e) {
                        // Ignore parse error
                    }
                    throw new Error(errorMessage);
                }
                return response.text();
            })
            .then(html => {
                document.documentElement.innerHTML = html;
            })
            .catch(error => {
                console.error('Error:', error);
                alert(error.message);
                loading.style.display = 'none';
                analyzeBtn.disabled = false;
            });
    });
});

// Clear image function
function clearImage() {
    const fileInput = document.getElementById('foodImage');
    const previewSection = document.getElementById('previewSection');
    const analyzeBtn = document.getElementById('analyzeBtn');

    fileInput.value = '';
    previewSection.style.display = 'none';
    analyzeBtn.disabled = true;
}