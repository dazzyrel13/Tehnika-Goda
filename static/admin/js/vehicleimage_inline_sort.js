/**
 * Горизонтальная сетка фото: тяните за само превью.
 */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    const group = document.getElementById("vehicleimage_set-group");
    if (!group) return;
    const grid = group.querySelector(".tg-photo-grid") || group;

    function allItems() {
      return Array.from(grid.querySelectorAll(".tg-photo-card")).filter(
        (el) =>
          !el.classList.contains("empty-form") &&
          !(el.id && String(el.id).endsWith("-empty"))
      );
    }

    function syncOrder() {
      allItems().forEach((item, index) => {
        const orderInput = item.querySelector("input[name$='-order']");
        if (orderInput) orderInput.value = String(index + 1);
      });
    }

    let dragItem = null;

    function onPointerDown(event) {
      if (event.button !== 0) return;
      const preview = event.target.closest(".tg-photo-card__preview");
      if (!preview || !grid.contains(preview)) return;
      const card = preview.closest(".tg-photo-card");
      if (!card || card.classList.contains("empty-form")) return;
      dragItem = card;
      card.classList.add("tg-row-dragging");
      try {
        preview.setPointerCapture(event.pointerId);
      } catch (e) {}
      event.preventDefault();
    }

    function onPointerMove(event) {
      if (!dragItem) return;
      const under = document.elementFromPoint(event.clientX, event.clientY);
      const over = under && under.closest(".tg-photo-card");
      if (!over || over === dragItem || over.classList.contains("empty-form")) return;
      if (!grid.contains(over)) return;
      const items = allItems();
      const dragIdx = items.indexOf(dragItem);
      const overIdx = items.indexOf(over);
      if (dragIdx < 0 || overIdx < 0) return;
      if (dragIdx < overIdx) over.after(dragItem);
      else over.before(dragItem);
    }

    function onPointerUp() {
      if (!dragItem) return;
      dragItem.classList.remove("tg-row-dragging");
      dragItem = null;
      syncOrder();
    }

    grid.addEventListener("pointerdown", onPointerDown);
    grid.addEventListener("pointermove", onPointerMove);
    grid.addEventListener("pointerup", onPointerUp);
    grid.addEventListener("pointercancel", onPointerUp);
    grid.addEventListener("dragstart", function (event) {
      event.preventDefault();
    });

    const form = group.closest("form");
    if (form) form.addEventListener("submit", syncOrder);
    syncOrder();
  });
})();
