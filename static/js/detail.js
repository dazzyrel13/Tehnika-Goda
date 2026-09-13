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
        const counterEl = document.getElementById("vehicle-gallery-counter");
        if (!mainImage || !thumbs.length) return;

        const thumbList = Array.from(thumbs);
        let activeIndex = 0;
        let suppressClick = false;

        const lightbox = document.getElementById("vehicle-lightbox");
        const lightboxImage = document.getElementById("vehicle-lightbox-image");
        const lightboxClose = lightbox
            ? lightbox.querySelector(".vehicle-lightbox__close")
            : null;
        const lightboxPrev = document.getElementById("vehicle-lightbox-prev");
        const lightboxNext = document.getElementById("vehicle-lightbox-next");
        const lightboxCounter = document.getElementById("vehicle-lightbox-counter");
        const lightboxStage = lightbox
            ? lightbox.querySelector(".vehicle-lightbox__stage")
            : null;

        const highlightThumb = (activeThumb) => {
            thumbs.forEach((el) => {
                el.classList.toggle("is-active", el === activeThumb);
            });
            if (activeThumb && typeof activeThumb.scrollIntoView === "function") {
                activeThumb.scrollIntoView({
                    behavior: "smooth",
                    inline: "nearest",
                    block: "nearest",
                });
            }
        };

        const syncNavVisibility = () => {
            const many = thumbList.length > 1;
            [prevBtn, nextBtn, lightboxPrev, lightboxNext].forEach((btn) => {
                if (!btn) return;
                btn.hidden = !many;
            });
            if (counterEl) counterEl.hidden = thumbList.length < 1;
            if (lightboxCounter) lightboxCounter.hidden = thumbList.length < 1;
        };

        const updateCounters = () => {
            const label = activeIndex + 1 + " / " + thumbList.length;
            if (counterEl) counterEl.textContent = label;
            if (lightboxCounter) lightboxCounter.textContent = label;
            syncNavVisibility();
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
            activeIndex = index;
            highlightThumb(thumb);
            updateCounters();
            if (lightbox && !lightbox.hidden) syncLightboxImage();
        };

        const showByIndex = (index) => {
            if (!thumbList.length) return;
            const normalized = ((index % thumbList.length) + thumbList.length) % thumbList.length;
            setMainImage(thumbList[normalized], normalized);
        };

        const syncLightboxImage = () => {
            if (!lightboxImage) return;
            const thumb = thumbList[activeIndex];
            const src =
                (thumb && thumb.dataset && thumb.dataset.fullSrc) ||
                mainImage.dataset.fullSrc ||
                mainImage.currentSrc ||
                mainImage.src;
            if (!src) return;
            lightboxImage.src = src;
            lightboxImage.alt = mainImage.alt || "";
            updateCounters();
        };

        const openLightbox = () => {
            if (!lightbox || !lightboxImage) return;
            syncLightboxImage();
            lightbox.hidden = false;
            document.body.classList.add("vehicle-lightbox-open");
            if (lightboxClose) lightboxClose.focus();
        };

        const closeLightbox = () => {
            if (!lightbox) return;
            lightbox.hidden = true;
            document.body.classList.remove("vehicle-lightbox-open");
            lightbox.style.backgroundColor = "";
            if (lightboxStage) lightboxStage.style.transform = "";
        };

        thumbs.forEach((thumb, index) => {
            thumb.addEventListener("click", () => {
                setMainImage(thumb, index);
            });
        });

        if (prevBtn) {
            prevBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                showByIndex(activeIndex - 1);
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                showByIndex(activeIndex + 1);
            });
        }

        if (lightboxPrev) {
            lightboxPrev.addEventListener("click", (event) => {
                event.stopPropagation();
                showByIndex(activeIndex - 1);
            });
        }
        if (lightboxNext) {
            lightboxNext.addEventListener("click", (event) => {
                event.stopPropagation();
                showByIndex(activeIndex + 1);
            });
        }

        mainImage.addEventListener("click", (event) => {
            if (suppressClick) {
                suppressClick = false;
                event.preventDefault();
                return;
            }
            event.preventDefault();
            openLightbox();
        });
        mainImage.addEventListener("dragstart", (event) => {
            event.preventDefault();
        });

        const galleryMain = mainImage.closest(".vehicle-gallery-main");
        if (galleryMain) {
            galleryMain.addEventListener("click", (event) => {
                if (event.target === galleryMain) openLightbox();
            });
        }

        if (lightbox) {
            lightbox.addEventListener("click", (event) => {
                if (
                    event.target === lightbox ||
                    event.target === lightboxClose ||
                    (event.target.classList &&
                        event.target.classList.contains("vehicle-lightbox__backdrop"))
                ) {
                    closeLightbox();
                }
            });
        }

        document.addEventListener("keydown", (event) => {
            const tag = (event.target && event.target.tagName) || "";
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
            if (event.target && event.target.isContentEditable) return;
            if (event.key === "Escape") {
                closeLightbox();
                return;
            }
            if (event.key === "ArrowLeft") {
                showByIndex(activeIndex - 1);
            }
            if (event.key === "ArrowRight") {
                showByIndex(activeIndex + 1);
            }
        });

        function bindSwipe(target, options) {
            if (!target) return;
            let startX = null;
            let startY = null;
            let tracking = false;
            const threshold = options.threshold || 40;
            const verticalClose = options.verticalClose || 0;

            target.addEventListener(
                "touchstart",
                (event) => {
                    if (!event.changedTouches || !event.changedTouches[0]) return;
                    startX = event.changedTouches[0].clientX;
                    startY = event.changedTouches[0].clientY;
                    tracking = true;
                    if (options.onStart) options.onStart();
                },
                { passive: true }
            );

            target.addEventListener(
                "touchmove",
                (event) => {
                    if (!tracking || startX === null || startY === null) return;
                    if (!event.changedTouches || !event.changedTouches[0]) return;
                    const x = event.changedTouches[0].clientX;
                    const y = event.changedTouches[0].clientY;
                    const dx = x - startX;
                    const dy = y - startY;
                    if (options.onMove) options.onMove(dx, dy);
                },
                { passive: true }
            );

            target.addEventListener(
                "touchend",
                (event) => {
                    if (!tracking || startX === null || startY === null) return;
                    const end = event.changedTouches && event.changedTouches[0];
                    const endX = end ? end.clientX : startX;
                    const endY = end ? end.clientY : startY;
                    const dx = endX - startX;
                    const dy = endY - startY;
                    tracking = false;
                    startX = null;
                    startY = null;

                    if (verticalClose && dy > verticalClose && Math.abs(dy) > Math.abs(dx)) {
                        if (options.onVerticalClose) options.onVerticalClose();
                        if (options.onEnd) options.onEnd(0, 0, true);
                        return;
                    }

                    if (Math.abs(dx) > threshold && Math.abs(dx) > Math.abs(dy)) {
                        if (options.onSwipe) options.onSwipe(dx);
                        if (options.suppressClickAfterSwipe) suppressClick = true;
                    }
                    if (options.onEnd) options.onEnd(dx, dy, false);
                },
                { passive: true }
            );

            target.addEventListener(
                "touchcancel",
                () => {
                    tracking = false;
                    startX = null;
                    startY = null;
                    if (options.onEnd) options.onEnd(0, 0, true);
                },
                { passive: true }
            );
        }

        bindSwipe(mainImage, {
            threshold: 36,
            suppressClickAfterSwipe: true,
            onSwipe: (dx) => {
                showByIndex(dx > 0 ? activeIndex - 1 : activeIndex + 1);
            },
        });

        const swipeTarget = lightboxStage || lightboxImage;
        bindSwipe(swipeTarget, {
            threshold: 36,
            verticalClose: 90,
            onMove: (dx, dy) => {
                if (!lightboxStage) return;
                if (Math.abs(dy) > Math.abs(dx) && dy > 0) {
                    const fade = Math.max(0.35, 1 - dy / 320);
                    lightboxStage.style.transform = "translateY(" + dy + "px)";
                    lightbox.style.backgroundColor = "rgba(10, 10, 14, " + fade + ")";
                } else if (Math.abs(dx) > 8) {
                    lightboxStage.style.transform = "translateX(" + dx * 0.35 + "px)";
                }
            },
            onSwipe: (dx) => {
                showByIndex(dx > 0 ? activeIndex - 1 : activeIndex + 1);
            },
            onVerticalClose: () => {
                closeLightbox();
            },
            onEnd: () => {
                if (!lightboxStage) return;
                lightboxStage.style.transform = "";
                lightbox.style.backgroundColor = "";
            },
        });

        const initialThumb = thumbList.find(
            (thumb) =>
                thumb.dataset.fullSrc === mainImage.dataset.fullSrc ||
                thumb.dataset.fullSrc === mainImage.getAttribute("src")
        );
        if (initialThumb) {
            activeIndex = thumbList.indexOf(initialThumb);
            highlightThumb(initialThumb);
        } else {
            highlightThumb(thumbList[0]);
        }
        updateCounters();
    });
})();
