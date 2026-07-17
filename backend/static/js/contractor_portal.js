(function () {
  "use strict";

  function initialise(form) {
    const rows = form.querySelector("[data-photo-rows]");
    const template = form.querySelector("template[data-photo-template]");
    const addButton = form.querySelector("[data-add-photo]");
    const submitButton = form.querySelector("[data-submit-delivery]");
    if (!rows || !template) return;

    const maximum = Number.parseInt(rows.dataset.max || "0", 10);
    let nextIndex = 1;

    function countRows() {
      return rows.querySelectorAll("[data-photo-row]").length;
    }

    function refreshAddButton() {
      if (!addButton) return;
      const isFull = countRows() >= maximum;
      addButton.hidden = maximum <= 0 || isFull;
      addButton.disabled = isFull;
    }

    function bindRow(row) {
      const input = row.querySelector("[data-photo-input]");
      const preview = row.querySelector("[data-photo-preview]");
      const filename = row.querySelector("[data-photo-name]");
      const cameraButton = row.querySelector("[data-open-camera]");
      const galleryButton = row.querySelector("[data-open-gallery]");
      const removeButton = row.querySelector("[data-remove-photo]");

      function openPicker(useCamera) {
        if (!input) return;
        if (useCamera) input.setAttribute("capture", "environment");
        else input.removeAttribute("capture");
        input.click();
      }

      if (cameraButton) cameraButton.addEventListener("click", function () { openPicker(true); });
      if (galleryButton) galleryButton.addEventListener("click", function () { openPicker(false); });
      if (removeButton) {
        removeButton.addEventListener("click", function () {
          row.remove();
          refreshAddButton();
          if (countRows() === 0 && maximum > 0) addRow();
        });
      }
      if (input) {
        input.addEventListener("change", function () {
          const file = input.files && input.files[0];
          if (filename) filename.textContent = file ? file.name : "—";
          if (!preview) return;
          if (!file) {
            preview.hidden = true;
            preview.removeAttribute("src");
            return;
          }
          preview.src = URL.createObjectURL(file);
          preview.hidden = false;
        });
      }
    }

    function addRow() {
      if (countRows() >= maximum) return;
      rows.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll("__INDEX__", String(nextIndex)));
      nextIndex += 1;
      bindRow(rows.lastElementChild);
      refreshAddButton();
    }

    if (addButton) addButton.addEventListener("click", addRow);
    if (maximum > 0) addRow();

    form.addEventListener("submit", function () {
      if (!submitButton) return;
      submitButton.disabled = true;
      submitButton.textContent = form.dataset.sendingLabel || "Sending…";
    });
  }

  document.querySelectorAll("form[data-contractor-delivery]").forEach(initialise);
})();
