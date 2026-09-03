(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") fn();
        else document.addEventListener("DOMContentLoaded", fn);
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === name + "=") {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    window.getCookie = getCookie;

    if ("serviceWorker" in navigator) {
        window.addEventListener("load", () => {
            navigator.serviceWorker.register("/sw.js").catch(() => {});
        });
    }

    function safeSameOrigin(url) {
        if (!url || typeof url !== "string") return "";
        try {
            const parsed = new URL(url, window.location.origin);
            if (parsed.origin !== window.location.origin) return "";
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (err) {
            return "";
        }
    }

    function createSearchRow(item) {
        const link = document.createElement("a");
        const href = safeSameOrigin(item.url);
        if (href) link.href = href;
        link.style.cssText =
            "display: flex; align-items: center; gap: 12px; padding: 12px; text-decoration: none; color: var(--text-main); border-bottom: 1px solid var(--glass-border); transition: background 0.2s;";

        const imageSrc = safeSameOrigin(item.image);
        if (imageSrc) {
            const img = document.createElement("img");
            img.src = imageSrc;
            img.alt = "";
            img.width = 40;
            img.height = 40;
            img.style.cssText =
                "width: 40px; height: 40px; border-radius: 6px; flex-shrink: 0; object-fit: cover;";
            link.appendChild(img);
        } else {
            const imgDiv = document.createElement("div");
            imgDiv.style.cssText =
                "width: 40px; height: 40px; border-radius: 6px; flex-shrink: 0; background: #eee;";
            link.appendChild(imgDiv);
        }

        const textDiv = document.createElement("div");
        textDiv.style.cssText = "flex: 1; overflow: hidden;";

        const titleEl = document.createElement("div");
        titleEl.style.cssText =
            "font-size: 13px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;";
        titleEl.textContent = item.title || "";

        const priceEl = document.createElement("div");
        priceEl.style.cssText = "font-size: 11px; color: var(--accent-red);";
        priceEl.textContent = item.price || "";

        textDiv.appendChild(titleEl);
        textDiv.appendChild(priceEl);
        link.appendChild(textDiv);
        return link;
    }

    function createEmptySearchRow() {
        const wrap = document.createElement("div");
        wrap.style.cssText = "padding: 14px 16px; color: var(--text-muted); font-size: 13px;";
        wrap.appendChild(document.createTextNode("Ничего не найдено. "));
        const leadLink = document.createElement("a");
        leadLink.href = "#leads-section";
        leadLink.style.cssText = "color: var(--text-main); font-weight: 700;";
        leadLink.textContent = "Оставить заявку на подбор";
        wrap.appendChild(leadLink);
        return wrap;
    }

    ready(function () {
        const searchInput = document.getElementById("global-search");
        const searchResults = document.getElementById("search-results");

        if (searchInput && searchResults) {
            const searchUrl =
                searchInput.dataset.searchUrl || "/catalog/search-ajax/";
            let searchTimeout;
            searchInput.addEventListener("input", function () {
                const q = this.value.trim();
                if (q.length < 2) {
                    searchResults.style.display = "none";
                    return;
                }

                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    const url =
                        searchUrl +
                        (searchUrl.indexOf("?") >= 0 ? "&" : "?") +
                        "q=" +
                        encodeURIComponent(q);
                    fetch(url)
                        .then((res) => res.json())
                        .then((data) => {
                            searchResults.replaceChildren();
                            if (data.length > 0) {
                                data.forEach((item) => {
                                    searchResults.appendChild(createSearchRow(item));
                                });
                            } else {
                                searchResults.appendChild(createEmptySearchRow());
                            }
                            searchResults.style.display = "block";
                        })
                        .catch(() => {
                            searchResults.style.display = "none";
                        });
                }, 250);
            });

            document.addEventListener("click", function (e) {
                if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                    searchResults.style.display = "none";
                }
            });
        }

        (function initCookieConsent() {
            const KEY = "tg_cookie_consent_v1";
            const LEGACY_KEY = "tdv_cookie_consent_v1";
            const banner = document.getElementById("cookie-consent");
            const acceptBtn = document.getElementById("cookie-accept");
            const necessaryBtn = document.getElementById("cookie-necessary");
            if (!banner || !acceptBtn || !necessaryBtn) return;

            const ymId = (document.body.dataset.yandexMetrikaId || "").trim();

            const loadYandexMetrika = (id) => {
                if (!id || window.__tgYmLoaded) return;
                window.__tgYmLoaded = true;
                (function (m, e, t, r, i, k, a) {
                    m[i] =
                        m[i] ||
                        function () {
                            (m[i].a = m[i].a || []).push(arguments);
                        };
                    m[i].l = 1 * new Date();
                    for (var j = 0; j < document.scripts.length; j++) {
                        if (document.scripts[j].src === r) return;
                    }
                    k = e.createElement(t);
                    a = e.getElementsByTagName(t)[0];
                    k.async = 1;
                    k.src = r;
                    a.parentNode.insertBefore(k, a);
                })(
                    window,
                    document,
                    "script",
                    "https://mc.yandex.ru/metrika/tag.js?id=" + encodeURIComponent(id),
                    "ym"
                );
                window.dataLayer = window.dataLayer || [];
                window.ym(Number(id), "init", {
                    ssr: true,
                    webvisor: true,
                    clickmap: true,
                    ecommerce: "dataLayer",
                    accurateTrackBounce: true,
                    trackLinks: true,
                });
            };

            let saved = localStorage.getItem(KEY);
            if (!saved && localStorage.getItem(LEGACY_KEY)) {
                saved = localStorage.getItem(LEGACY_KEY);
                localStorage.setItem(KEY, saved);
            }
            if (!saved) banner.style.display = "block";
            else if (saved === "accepted") loadYandexMetrika(ymId);

            const saveChoice = (value) => {
                localStorage.setItem(KEY, value);
                banner.style.display = "none";
                if (value === "accepted") loadYandexMetrika(ymId);
            };

            acceptBtn.addEventListener("click", () => saveChoice("accepted"));
            necessaryBtn.addEventListener("click", () => saveChoice("necessary"));
        })();

        (function initLeadForm() {
            const params = new URLSearchParams(window.location.search);
            const utmSource = document.getElementById("lead-utm-source");
            const utmMedium = document.getElementById("lead-utm-medium");
            const utmCampaign = document.getElementById("lead-utm-campaign");
            if (utmSource) utmSource.value = params.get("utm_source") || "";
            if (utmMedium) utmMedium.value = params.get("utm_medium") || "";
            if (utmCampaign) utmCampaign.value = params.get("utm_campaign") || "";

            const formTs = document.getElementById("lead-form-ts");
            const stampFormTs = () => {
                if (!formTs || formTs.dataset.stamped === "1") return;
                formTs.value = String(Date.now() / 1000);
                formTs.dataset.stamped = "1";
            };

            const vehicleInput = document.getElementById("lead-vehicle-id");
            const messageInput = document.getElementById("lead-message");
            document.querySelectorAll(".js-price-key-btn").forEach((btn) => {
                btn.addEventListener("click", (event) => {
                    event.preventDefault();
                    if (vehicleInput) vehicleInput.value = btn.dataset.vehicleId || "";
                    if (messageInput) {
                        messageInput.value =
                            "Прошу рассчитать стоимость под ключ и подтвердить наличие: " +
                            (btn.dataset.vehicleTitle || "");
                    }
                    const section = document.getElementById("leads-section");
                    if (section) section.scrollIntoView({ behavior: "smooth", block: "start" });
                });
            });

            const phoneInput = document.getElementById("lead-phone");
            const phoneHint = document.getElementById("lead-phone-hint");
            const leadForm = document.getElementById("lead-form");

            const formatRuPhone = (raw) => {
                let digits = String(raw || "").replace(/\D/g, "");
                if (digits.startsWith("8")) digits = "7" + digits.slice(1);
                if (digits && !digits.startsWith("7")) digits = "7" + digits;
                digits = digits.slice(0, 11);
                let out = "+7";
                if (digits.length > 1) out += " (" + digits.slice(1, 4);
                if (digits.length >= 4) out += ") " + digits.slice(4, 7);
                if (digits.length >= 7) out += "-" + digits.slice(7, 9);
                if (digits.length >= 9) out += "-" + digits.slice(9, 11);
                return out;
            };

            const isValidRuPhone = (raw) => {
                let digits = String(raw || "").replace(/\D/g, "");
                if (digits.startsWith("8") && digits.length === 11) {
                    digits = "7" + digits.slice(1);
                }
                if (digits.length === 10 && digits.startsWith("9")) digits = "7" + digits;
                return digits.length === 11 && digits.startsWith("7") && digits[1] !== "0";
            };

            if (phoneInput) {
                phoneInput.addEventListener("focus", () => {
                    if (!phoneInput.value.trim()) phoneInput.value = "+7 (";
                });
                phoneInput.addEventListener("input", () => {
                    phoneInput.value = formatRuPhone(phoneInput.value);
                    if (phoneHint) phoneHint.style.display = "none";
                    if (document.activeElement === phoneInput) {
                        const pos = phoneInput.value.length;
                        phoneInput.setSelectionRange(pos, pos);
                    }
                });
            }

            if (leadForm) {
                ["focusin", "input", "pointerdown"].forEach((ev) => {
                    leadForm.addEventListener(ev, stampFormTs, { passive: true });
                });

                const reachLeadGoal = () => {
                    const id = (document.body.dataset.yandexMetrikaId || "").trim();
                    if (!id || typeof window.ym !== "function") return;
                    try {
                        window.ym(Number(id), "reachGoal", "lead_submit");
                    } catch (_) {
                        /* Metrika blocked / unavailable */
                    }
                };

                const showLeadFeedback = (text, isError) => {
                    let box = document.getElementById("lead-form-feedback");
                    if (!box) {
                        box = document.createElement("div");
                        box.id = "lead-form-feedback";
                        box.className = "glass-panel";
                        box.style.cssText =
                            "padding: 15px; margin-bottom: 20px; border-color: var(--accent-yellow); background: rgba(255, 179, 0, 0.12);";
                        leadForm.parentNode.insertBefore(box, leadForm);
                    }
                    box.style.borderColor = isError ? "#b45309" : "var(--accent-yellow)";
                    box.textContent = text;
                };

                leadForm.addEventListener("submit", (event) => {
                    if (phoneInput && !isValidRuPhone(phoneInput.value)) {
                        event.preventDefault();
                        if (phoneHint) phoneHint.style.display = "block";
                        phoneInput.focus();
                        return;
                    }

                    // Prefer AJAX so we can fire Metrika reachGoal only on real success.
                    event.preventDefault();
                    stampFormTs();
                    const submitBtn = leadForm.querySelector('[type="submit"]');
                    if (submitBtn) submitBtn.disabled = true;

                    const body = new FormData(leadForm);
                    fetch(leadForm.action, {
                        method: "POST",
                        body,
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            Accept: "application/json",
                        },
                        credentials: "same-origin",
                    })
                        .then(async (response) => {
                            let payload = {};
                            try {
                                payload = await response.json();
                            } catch (_) {
                                payload = {};
                            }
                            if (!response.ok || payload.status !== "success") {
                                const errors = payload.errors || {};
                                const first =
                                    (errors.__all__ && errors.__all__[0]) ||
                                    (errors.phone && errors.phone[0]) ||
                                    (errors.city && errors.city[0]) ||
                                    (errors.name && errors.name[0]) ||
                                    "Не удалось отправить заявку. Проверьте данные.";
                                showLeadFeedback(first, true);
                                return;
                            }
                            reachLeadGoal();
                            showLeadFeedback(
                                payload.message ||
                                    "Заявка успешно отправлена! Свяжемся в течение 15 минут в рабочее время.",
                                false
                            );
                            leadForm.reset();
                            if (formTs) {
                                formTs.value = "";
                                delete formTs.dataset.stamped;
                            }
                            if (vehicleInput) vehicleInput.value = "";
                        })
                        .catch(() => {
                            showLeadFeedback(
                                "Сеть недоступна. Попробуйте ещё раз через минуту.",
                                true
                            );
                        })
                        .finally(() => {
                            if (submitBtn) submitBtn.disabled = false;
                        });
                });
            }
        })();

        (function initMobileNav() {
            const burger = document.getElementById("nav-burger");
            const nav = document.getElementById("site-nav");
            if (!burger || !nav) return;

            const mq = window.matchMedia("(max-width: 991px)");

            const setOpen = (open) => {
                document.body.classList.toggle("is-nav-open", open);
                burger.classList.toggle("is-open", open);
                burger.setAttribute("aria-expanded", open ? "true" : "false");
                burger.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
                if (!open) {
                    nav.querySelectorAll(".nav-dropdown.is-open").forEach((el) => {
                        el.classList.remove("is-open");
                    });
                }
            };

            burger.addEventListener("click", () => {
                setOpen(!document.body.classList.contains("is-nav-open"));
            });

            document.addEventListener("keydown", (event) => {
                if (event.key === "Escape") setOpen(false);
            });

            nav.querySelectorAll(".nav-dropdown > a").forEach((link) => {
                link.addEventListener("click", (event) => {
                    if (!mq.matches) return;
                    const item = link.parentElement;
                    // Second tap on an open section follows the link.
                    if (item.classList.contains("is-open")) {
                        setOpen(false);
                        return;
                    }
                    event.preventDefault();
                    nav.querySelectorAll(".nav-dropdown.is-open").forEach((el) => {
                        if (el !== item) el.classList.remove("is-open");
                    });
                    item.classList.add("is-open");
                });
            });

            nav.querySelectorAll(".nav-links a").forEach((link) => {
                link.addEventListener("click", () => {
                    if (!mq.matches) return;
                    if (link.parentElement.classList.contains("nav-dropdown") && link.parentElement.querySelector(":scope > a") === link) {
                        return;
                    }
                    setOpen(false);
                });
            });

            const onMqChange = () => {
                if (!mq.matches) setOpen(false);
            };
            if (typeof mq.addEventListener === "function") {
                mq.addEventListener("change", onMqChange);
            } else if (typeof mq.addListener === "function") {
                mq.addListener(onMqChange);
            }
        })();

        (function initHeaderAndReveal() {
            const header = document.querySelector("header");
            const onScroll = () => {
                if (!header) return;
                header.classList.toggle("is-scrolled", window.scrollY > 12);
            };
            onScroll();
            window.addEventListener("scroll", onScroll, { passive: true });

            const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            const nodes = document.querySelectorAll(".reveal");
            if (!nodes.length) return;

            if (reduce || !("IntersectionObserver" in window)) {
                nodes.forEach((el) => el.classList.add("is-visible"));
                return;
            }

            const io = new IntersectionObserver(
                (entries) => {
                    entries.forEach((entry) => {
                        if (!entry.isIntersecting) return;
                        const el = entry.target;
                        el.style.willChange = "opacity, transform";
                        el.classList.add("is-visible");
                        io.unobserve(el);
                        window.setTimeout(() => {
                            el.style.willChange = "auto";
                        }, 800);
                    });
                },
                { threshold: 0.14, rootMargin: "0px 0px -6% 0px" }
            );

            nodes.forEach((el) => io.observe(el));
        })();
    });
})();
