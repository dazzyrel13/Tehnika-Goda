/**
 * Порядок фото галереи в админке: тяните карточку за ⠿ или за превью.
 * Не за ссылку «На данный момент» — браузер тогда открывает «искать в новой вкладке».
 */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function isControl(el) {
    return !!(el && el.closest && el.closest("input, select, textarea, button, a, .delete"));
  }

  ready(function () {
    const group = document.getElementById("vehicleimage_set-group");
    if (!group) return;

    const tbody =
      group.querySelector("fieldset table tbody") || group.querySelector("tbody");

    function allItems() {
      const stacked = Array.from(group.querySelectorAll(".inline-related")).filter(
        (el) =>
          !el.classList.contains("empty-form") &&
          !(el.id && String(el.id).endsWith("-empty")) &&
          !el.querySelector("table")
      );
      if (stacked.length) {
        return stacked.filter((el) => {
          const del = el.querySelector("input[name$='-DELETE']");
          return !(del && del.checked);
        });
      }
      if (!tbody) return [];
      return Array.from(tbody.querySelectorAll("tr.form-row")).filter((row) => {
        if (row.classList.contains("empty-form")) return false;
        if (row.id && String(row.id).endsWith("-empty")) return false;
        const del = row.querySelector("input[name$='-DELETE']");
        return !(del && del.checked);
      });
    }

    function parentOf(item) {
      return item.parentNode;
    }

    function syncOrder() {
      allItems().forEach((item, index) => {
        const orderInput = item.querySelector("input[name$='-order']");
        if (orderInput) orderInput.value = String(index + 1);
      });
    }

    function disableNativeFileDrag(root) {
      root.querySelectorAll("img, a").forEach((el) => {
        el.setAttribute("draggable", "false");
        el.addEventListener("dragstart", function (event) {
          event.preventDefault();
        });
      });
    }

    let dragItem = null;

    function prepare(item) {
      if (item.dataset.tgSortReady === "1") return;
      item.dataset.tgSortReady = "1";
      item.classList.add("tg-sortable-row");
      item.draggable = false;
      disableNativeFileDrag(item);

      item.addEventListener("mousedown", function (event) {
        if (event.button !== 0) return;
        if (isControl(event.target)) {
          item.draggable = false;
          return;
        }
        item.draggable = true;
      });
      item.addEventListener("mouseup", function () {
        item.draggable = false;
      });

      item.addEventListener("dragstart", function (event) {
        if (isControl(event.target) || !item.draggable) {
          event.preventDefault();
          return;
        }
        dragItem = item;
        item.classList.add("tg-row-dragging");
        event.dataTransfer.effectAllowed = "move";
        try {
          event.dataTransfer.setData("text/plain", item.id || "row");
        } catch (e) {}
        if (event.dataTransfer.setDragImage) {
          event.dataTransfer.setDragImage(item, 24, 24);
        }
      });

      item.addEventListener("dragend", function () {
        item.classList.remove("tg-row-dragging");
        item.draggable = false;
        group.querySelectorAll(".tg-row-drag-over").forEach(function (el) {
          el.classList.remove("tg-row-drag-over");
        });
        dragItem = null;
        syncOrder();
      });

      item.addEventListener("dragover", function (event) {
        if (!dragItem || dragItem === item) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        item.classList.add("tg-row-drag-over");
      });

      item.addEventListener("dragleave", function () {
        item.classList.remove("tg-row-drag-over");
      });

      item.addEventListener("drop", function (event) {
        event.preventDefault();
        item.classList.remove("tg-row-drag-over");
        if (!dragItem || dragItem === item) return;
        const rect = item.getBoundingClientRect();
        const after = event.clientY > rect.top + rect.height / 2;
        const parent = parentOf(item);
        if (after) parent.insertBefore(dragItem, item.nextSibling);
        else parent.insertBefore(dragItem, item);
        syncOrder();
      });
    }

    function init() {
      allItems().forEach(prepare);
      syncOrder();
    }

    init();
    new MutationObserver(init).observe(group, { childList: true, subtree: true });

    const form = group.closest("form");
    if (form) form.addEventListener("submit", syncOrder);
  });
})();
