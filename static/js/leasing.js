(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") fn();
        else document.addEventListener("DOMContentLoaded", fn);
    }

    ready(function () {
        const priceRange = document.getElementById("priceRange");
        const prepayRange = document.getElementById("prepayRange");
        const termRange = document.getElementById("termRange");
        const priceVal = document.getElementById("priceVal");
        const prepayVal = document.getElementById("prepayVal");
        const termVal = document.getElementById("termVal");
        const monthlyResult = document.getElementById("monthlyResult");
        if (!priceRange || !prepayRange || !termRange || !priceVal || !prepayVal || !termVal || !monthlyResult) {
            return;
        }

        function updateCalc() {
            const price = parseInt(priceRange.value, 10);
            const prepayPct = parseInt(prepayRange.value, 10);
            const term = parseInt(termRange.value, 10);
            const rate = 0.105 / 12;

            priceVal.innerText = price.toLocaleString("ru-RU");
            prepayVal.innerText = String(prepayPct);
            termVal.innerText = String(term);

            const loanAmount = price * (1 - prepayPct / 100);
            const monthly =
                (loanAmount * rate * Math.pow(1 + rate, term)) /
                (Math.pow(1 + rate, term) - 1);

            monthlyResult.innerText = Math.round(monthly).toLocaleString("ru-RU") + " ₽";
        }

        [priceRange, prepayRange, termRange].forEach((el) => {
            el.addEventListener("input", updateCalc);
        });
        updateCalc();
    });
})();
