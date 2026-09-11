(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") fn();
        else document.addEventListener("DOMContentLoaded", fn);
    }

    ready(function () {
        const writeEl = document.querySelector("[data-warranty-write]");
        if (writeEl) {
            const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            const ensureCaveat = () => {
                if (!document.fonts || !document.fonts.load) {
                    return Promise.resolve();
                }
                return document.fonts
                    .load('700 2.35em "Caveat"')
                    .then(() => document.fonts.ready)
                    .catch(() => undefined);
            };
            const startWrite = () => {
                if (writeEl.classList.contains("is-writing") || writeEl.classList.contains("is-written")) {
                    return;
                }
                ensureCaveat().then(() => {
                    if (writeEl.classList.contains("is-writing") || writeEl.classList.contains("is-written")) {
                        return;
                    }
                    if (reduce) {
                        writeEl.classList.add("is-written");
                        return;
                    }
                    writeEl.classList.add("is-writing");
                    window.setTimeout(() => {
                        writeEl.classList.remove("is-writing");
                        writeEl.classList.add("is-written");
                    }, 2900);
                });
            };

            if ("IntersectionObserver" in window) {
                const io = new IntersectionObserver(
                    (entries) => {
                        entries.forEach((entry) => {
                            if (!entry.isIntersecting) return;
                            startWrite();
                            io.disconnect();
                        });
                    },
                    { threshold: 0.35 }
                );
                const section = writeEl.closest(".ed-warranty") || writeEl;
                io.observe(section);
            } else {
                startWrite();
            }
        }

        document.querySelectorAll(".js-review-text").forEach((textEl) => {
            const moreBtn = textEl.parentElement && textEl.parentElement.querySelector(".js-review-more");
            if (!moreBtn) return;

            textEl.classList.add("is-clamped");
            const needsToggle = textEl.scrollHeight > textEl.clientHeight + 2;
            if (!needsToggle) {
                textEl.classList.remove("is-clamped");
                return;
            }

            moreBtn.hidden = false;
            moreBtn.addEventListener("click", () => {
                const expanded = textEl.classList.toggle("is-expanded");
                textEl.classList.toggle("is-clamped", !expanded);
                moreBtn.textContent = expanded ? "Свернуть" : "Читать целиком";
            });
        });

        const reviewsCarousel = document.querySelector(".home-reviews-carousel");
        if (reviewsCarousel) {
            const scroller = reviewsCarousel.querySelector(".js-reviews-scroller");
            const prevBtn = reviewsCarousel.querySelector(".js-reviews-prev");
            const nextBtn = reviewsCarousel.querySelector(".js-reviews-next");
            const hint = reviewsCarousel.querySelector(".js-reviews-hint");
            const mq = window.matchMedia("(max-width: 960px)");

            const cardStep = () => {
                const card = scroller && scroller.querySelector(".home-review");
                if (!card) return 280;
                const styles = window.getComputedStyle(scroller);
                const gap = parseFloat(styles.columnGap || styles.gap || "12") || 12;
                return card.getBoundingClientRect().width + gap;
            };

            const syncNav = () => {
                if (!scroller || !prevBtn || !nextBtn) return;
                const mobile = mq.matches;
                const maxScroll = scroller.scrollWidth - scroller.clientWidth;
                const canScroll = mobile && maxScroll > 8;
                reviewsCarousel.classList.toggle("has-scroll", canScroll);
                prevBtn.hidden = !canScroll;
                nextBtn.hidden = !canScroll;
                if (hint) hint.hidden = !canScroll;
                if (!canScroll) return;
                const atStart = scroller.scrollLeft <= 4;
                const atEnd = scroller.scrollLeft >= maxScroll - 4;
                prevBtn.disabled = atStart;
                nextBtn.disabled = atEnd;
                if (hint) hint.hidden = !atStart;
            };

            const scrollByDir = (dir) => {
                if (!scroller) return;
                scroller.scrollBy({ left: dir * cardStep(), behavior: "smooth" });
            };

            if (prevBtn) prevBtn.addEventListener("click", () => scrollByDir(-1));
            if (nextBtn) nextBtn.addEventListener("click", () => scrollByDir(1));
            if (scroller) {
                scroller.addEventListener("scroll", syncNav, { passive: true });
                window.addEventListener("resize", syncNav);
                if (typeof mq.addEventListener === "function") mq.addEventListener("change", syncNav);
                else if (typeof mq.addListener === "function") mq.addListener(syncNav);
                syncNav();
            }
        }

        const picker = document.querySelector("[data-home-picker]");
        if (picker) {
            const tabs = picker.querySelectorAll("[data-picker-tab]");
            const panels = picker.querySelectorAll("[data-picker-panel]");
            const activate = (slug) => {
                tabs.forEach((tab) => {
                    const on = tab.dataset.pickerTab === slug;
                    tab.classList.toggle("is-active", on);
                    tab.setAttribute("aria-selected", on ? "true" : "false");
                });
                panels.forEach((panel) => {
                    panel.hidden = panel.dataset.pickerPanel !== slug;
                });
                picker.querySelectorAll(".tdv-select.open").forEach((el) => el.classList.remove("open"));
            };
            tabs.forEach((tab) => {
                tab.addEventListener("click", () => activate(tab.dataset.pickerTab));
            });
        }

        const processCards = document.querySelectorAll(".process-grid--steps .process-card");
        if (processCards.length) {
            const mq = window.matchMedia("(max-width: 960px)");
            const syncProcess = () => {
                processCards.forEach((card, index) => {
                    card.open = mq.matches ? index === 0 : true;
                });
            };
            processCards.forEach((card) => {
                card.addEventListener("toggle", () => {
                    if (!mq.matches || !card.open) return;
                    processCards.forEach((other) => {
                        if (other !== card) other.open = false;
                    });
                });
            });
            if (mq.addEventListener) mq.addEventListener("change", syncProcess);
            else if (mq.addListener) mq.addListener(syncProcess);
            syncProcess();
        }

        const searchFold = document.querySelector(".home-deep-search__fold");
        if (searchFold) {
            const mqSearch = window.matchMedia("(max-width: 960px)");
            const syncSearchFold = () => {
                searchFold.open = !mqSearch.matches;
            };
            if (mqSearch.addEventListener) mqSearch.addEventListener("change", syncSearchFold);
            else if (mqSearch.addListener) mqSearch.addListener(syncSearchFold);
            syncSearchFold();
        }

        const selects = document.querySelectorAll(".home-deep-search select");
        if (!selects.length) return;

        const closeAll = () => {
            document.querySelectorAll(".tdv-select.open").forEach((el) => el.classList.remove("open"));
        };

        selects.forEach((selectEl) => {
            const wrapper = document.createElement("div");
            wrapper.className = "tdv-select";

            const trigger = document.createElement("button");
            trigger.type = "button";
            trigger.className = "tdv-select__trigger";
            trigger.textContent = (selectEl.options[selectEl.selectedIndex] && selectEl.options[selectEl.selectedIndex].text) || "Выбрать";

            const dropdown = document.createElement("div");
            dropdown.className = "tdv-select__dropdown";

            Array.from(selectEl.options).forEach((opt) => {
                const optionBtn = document.createElement("button");
                optionBtn.type = "button";
                optionBtn.className = "tdv-select__option";
                optionBtn.textContent = opt.text;
                optionBtn.dataset.value = opt.value;
                if (opt.selected && opt.value !== "") optionBtn.classList.add("is-selected");

                optionBtn.addEventListener("click", () => {
                    selectEl.value = opt.value;
                    trigger.textContent = opt.text;
                    dropdown.querySelectorAll(".tdv-select__option").forEach((o) => o.classList.remove("is-selected"));
                    if (opt.value !== "") optionBtn.classList.add("is-selected");
                    wrapper.classList.remove("open");
                    selectEl.dispatchEvent(new Event("change", { bubbles: true }));
                });

                dropdown.appendChild(optionBtn);
            });

            trigger.addEventListener("click", (e) => {
                e.preventDefault();
                const isOpen = wrapper.classList.contains("open");
                closeAll();
                if (!isOpen) wrapper.classList.add("open");
            });

            wrapper.appendChild(trigger);
            wrapper.appendChild(dropdown);

            selectEl.classList.add("tdv-select-native");
            selectEl.parentNode.insertBefore(wrapper, selectEl.nextSibling);
        });

        document.addEventListener("click", (e) => {
            if (!e.target.closest(".tdv-select")) closeAll();
        });
    });
})();
