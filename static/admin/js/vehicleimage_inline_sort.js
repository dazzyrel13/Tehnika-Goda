/**
 * Drag-and-drop порядок фото в инлайне VehicleImage.
 * Перетаскивание только за ручку ⠿.
 */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    const group = document.getElementById("vehicleimage_set-group");
    if (!group) return;

    const tbody =
      group.querySelector("fieldset table tbody") || group.querySelector("tbody");
    if (!tbody) return;

    let dragRow = null;

    function allDataRows() {
      return Array.from(tbody.querySelectorAll("tr.form-row")).filter((row) => {
        if (row.classList.contains("empty-form")) return false;
        if (row.id && String(row.id).endsWith("-empty")) return false;
        const del = row.querySelector("input[name$='-DELETE']");
        return !(del && del.checked);
      });
    }

    function syncOrder() {
      allDataRows().forEach((row, index) => {
        const orderInput = row.querySelector("input[name$='-order']");
        if (orderInput) orderInput.value = String(index + 1);
      });
    }

    function prepare(row) {
      if (row.dataset.tgSortReady === "1") return;
      row.dataset.tgSortReady = "1";
      row.classList.add("tg-sortable-row");
      row.draggable = false;

      const handle = row.querySelector(".drag-handle");
      if (handle) {
        handle.addEventListener("mousedown", function () {
          row.draggable = true;
        });
        handle.addEventListener("mouseup", function () {
          row.draggable = false;
        });
      }

      row.addEventListener("dragstart", function (event) {
        if (!row.draggable) {
          event.preventDefault();
          return;
        }
        dragRow = row;
        row.classList.add("tg-row-dragging");
        event.dataTransfer.effectAllowed = "move";
        try {
          event.dataTransfer.setData("text/plain", row.id || "row");
        } catch (e) {}
      });

      row.addEventListener("dragend", function () {
        row.classList.remove("tg-row-dragging");
        row.draggable = false;
        tbody.querySelectorAll(".tg-row-drag-over").forEach(function (el) {
          el.classList.remove("tg-row-drag-over");
        });
        dragRow = null;
        syncOrder();
      });

      row.addEventListener("dragover", function (event) {
        if (!dragRow || dragRow === row) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        row.classList.add("tg-row-drag-over");
      });

      row.addEventListener("dragleave", function () {
        row.classList.remove("tg-row-drag-over");
      });

      row.addEventListener("drop", function (event) {
        event.preventDefault();
        row.classList.remove("tg-row-drag-over");
        if (!dragRow || dragRow === row) return;

        const rect = row.getBoundingClientRect();
        const after = event.clientY > rect.top + rect.height / 2;
        if (after) {
          row.parentNode.insertBefore(dragRow, row.nextSibling);
        } else {
          row.parentNode.insertBefore(dragRow, row);
        }
        syncOrder();
      });
    }

    function init() {
      allDataRows().forEach(prepare);
      syncOrder();
    }

    init();
    new MutationObserver(init).observe(tbody, { childList: true });

    const form = group.closest("form");
    if (form) form.addEventListener("submit", syncOrder);
  });
})();
