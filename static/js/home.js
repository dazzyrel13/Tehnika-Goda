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
