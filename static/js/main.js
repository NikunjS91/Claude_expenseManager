// main.js — students will add JavaScript here as features are built

(function () {
    const modal   = document.getElementById('video-modal');
    const openBtn = document.getElementById('open-video-modal');
    const closeBtn = document.getElementById('close-video-modal');
    const iframe  = document.getElementById('video-iframe');

    if (!modal || !openBtn) return;

    function openModal() {
        // Lazy-load the iframe src on first open
        if (!iframe.src || iframe.src === window.location.href) {
            iframe.src = iframe.dataset.src;
        }
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        // Stop video by clearing src, restore so it can reopen cleanly
        iframe.src = '';
    }

    openBtn.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);

    // Close on backdrop click (but not on the modal box itself)
    modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
    });

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.classList.contains('is-open')) closeModal();
    });
}());
