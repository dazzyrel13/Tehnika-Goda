(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") fn();
        else document.addEventListener("DOMContentLoaded", fn);
    }

    ready(function () {
        const mainImage = document.getElementById("vehicle-main-image");
        const thumbs = document.querySelectorAll(".vehicle-gallery-thumb");
        const prevBtn = document.getElementById("vehicle-gallery-prev");
        const nextBtn = document.getElementById("vehicle-gallery-next");
        if (!mainImage || !thumbs.length) return;
        const thumbList = Array.from(thumbs);
        let activeIndex = -1;

        const highlightThumb = (activeThumb) => {
            thumbs.forEach((el) => {
                el.style.borderColor = "var(--glass-border)";
                el.style.boxShadow = "none";
            });
            if (activeThumb) {
                activeThumb.style.borderColor = "var(--accent-red)";
                activeThumb.style.boxShadow = "0 0 14px rgba(255, 179, 0, 0.28)";
            }
        };

        const setMainImage = (thumb, index) => {
            const fullSrc = thumb && thumb.dataset ? thumb.dataset.fullSrc : "";
            const displaySrc =
                (thumb && thumb.dataset && thumb.dataset.displaySrc) || fullSrc;
            const srcset = (thumb && thumb.dataset && thumb.dataset.srcset) || "";
            if (!fullSrc && !displaySrc) return;
            mainImage.src = displaySrc;
            if (srcset) {
                mainImage.srcset = srcset;
            } else {
                mainImage.removeAttribute("srcset");
            }
            mainImage.dataset.fullSrc = fullSrc || displaySrc;
            activeIndex = index || 0;
            highlightThumb(thumb);
        };

        const showByIndex = (index) => {
            if (!thumbList.length) return;
            const normalized = (index + thumbList.length) % thumbList.length;
            const thumb = thumbList[normalized];
            setMainImage(thumb, normalized);
        };

        thumbs.forEach((thumb, index) => {
            thumb.addEventListener("click", () => {
                setMainImage(thumb, index);
            });
        });

        if (prevBtn) {
            prevBtn.addEventListener("click", () => {
                showByIndex(activeIndex < 0 ? thumbList.length - 1 : activeIndex - 1);
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener("click", () => {
                showByIndex(activeIndex < 0 ? 0 : activeIndex + 1);
            });
        }

        document.addEventListener("keydown", (event) => {
            const tag = (event.target && event.target.tagName) || "";
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
            if (event.target && event.target.isContentEditable) return;
            if (event.key === "ArrowLeft") {
                showByIndex(activeIndex < 0 ? thumbList.length - 1 : activeIndex - 1);
            }
            if (event.key === "ArrowRight") {
                showByIndex(activeIndex < 0 ? 0 : activeIndex + 1);
            }
        });

        let touchStartX = null;
        mainImage.addEventListener(
            "touchstart",
            (event) => {
                touchStartX =
                    event.changedTouches && event.changedTouches[0]
                        ? event.changedTouches[0].clientX
                        : null;
            },
            { passive: true }
        );
        mainImage.addEventListener(
            "touchend",
            (event) => {
                if (touchStartX === null) return;
                const touchEndX =
                    event.changedTouches && event.changedTouches[0]
                        ? event.changedTouches[0].clientX
                        : touchStartX;
                const deltaX = touchEndX - touchStartX;
                if (Math.abs(deltaX) > 40) {
                    if (deltaX > 0) {
                        showByIndex(
                            activeIndex < 0 ? thumbList.length - 1 : activeIndex - 1
                        );
                    } else {
                        showByIndex(activeIndex < 0 ? 0 : activeIndex + 1);
                    }
                }
                touchStartX = null;
            },
            { passive: true }
        );

        mainImage.addEventListener("click", () => {
            const full = mainImage.dataset.fullSrc || mainImage.src;
            window.open(full, "_blank", "noopener,noreferrer");
        });

        const initialThumb = Array.from(thumbs).find(
            (thumb) =>
                thumb.dataset.fullSrc === mainImage.dataset.fullSrc ||
                thumb.dataset.fullSrc === mainImage.getAttribute("src")
        );
        if (initialThumb) {
            activeIndex = thumbList.indexOf(initialThumb);
            highlightThumb(initialThumb);
        }
    });
})();
