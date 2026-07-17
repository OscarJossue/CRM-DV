(function () {
  "use strict";

  function confirmExistingPhotoDelete(button) {
    button.addEventListener("click", function (event) {
      const message = button.dataset.confirm || "Delete this photo?";
      if (!window.confirm(message)) event.preventDefault();
    });
  }

  function initialiseDelivery(form) {
    const rows = form.querySelector("[data-photo-rows]");
    const template = form.querySelector("template[data-photo-template]");
    const addButton = form.querySelector("[data-add-photo]");
    const submitButton = form.querySelector("[data-submit-delivery]");
    const counter = form.querySelector("[data-photo-counter]");
    const remainingLabel = form.querySelector("[data-photo-remaining]");
    const existingCount = Number.parseInt(form.dataset.existingCount || "0", 10);
    const photoLimit = Number.parseInt(form.dataset.photoLimit || "5", 10);

    if (!rows || !template) {
      form.addEventListener("submit", function (event) {
        if (event.submitter && event.submitter.matches("[data-existing-photo-delete]")) return;
        if (!submitButton) return;
        submitButton.disabled = true;
        const label = submitButton.querySelector("span");
        if (label) label.textContent = form.dataset.sendingLabel || "Sending…";
      });
      return;
    }

    const maximumNew = Number.parseInt(rows.dataset.max || "0", 10);
    let nextIndex = 1;

    function allRows() {
      return Array.from(rows.querySelectorAll("[data-photo-row]"));
    }

    function selectedCount() {
      return allRows().filter(function (row) {
        const input = row.querySelector("[data-photo-input]");
        return Boolean(input && input.files && input.files.length);
      }).length;
    }

    function refreshStatus() {
      const selected = selectedCount();
      const total = Math.min(photoLimit, existingCount + selected);
      if (counter) counter.textContent = total + "/" + photoLimit;
      if (remainingLabel) remainingLabel.textContent = String(Math.max(0, photoLimit - total));
      if (addButton) {
        const isFull = allRows().length >= maximumNew;
        addButton.hidden = maximumNew <= 0 || isFull;
        addButton.disabled = isFull;
      }
    }

    function revokePreview(preview) {
      if (!preview || !preview.dataset.objectUrl) return;
      URL.revokeObjectURL(preview.dataset.objectUrl);
      delete preview.dataset.objectUrl;
    }

    function resetRow(row) {
      const input = row.querySelector("[data-photo-input]");
      const preview = row.querySelector("[data-photo-preview]");
      const filename = row.querySelector("[data-photo-name]");
      const description = row.querySelector("textarea");
      revokePreview(preview);
      if (input) input.value = "";
      if (preview) {
        preview.hidden = true;
        preview.removeAttribute("src");
      }
      if (filename) filename.textContent = filename.dataset.emptyLabel || filename.textContent;
      if (description) description.value = "";
      row.classList.remove("has-photo");
      refreshStatus();
    }

    function bindRow(row) {
      const input = row.querySelector("[data-photo-input]");
      const preview = row.querySelector("[data-photo-preview]");
      const filename = row.querySelector("[data-photo-name]");
      const cameraButton = row.querySelector("[data-open-camera]");
      const galleryButton = row.querySelector("[data-open-gallery]");
      const removeButton = row.querySelector("[data-remove-photo]");

      if (filename) filename.dataset.emptyLabel = filename.textContent;

      function openPicker(useCamera) {
        if (!input) return;
        if (useCamera) input.setAttribute("capture", "environment");
        else input.removeAttribute("capture");
        input.click();
      }

      if (cameraButton) cameraButton.addEventListener("click", function () { openPicker(true); });
      if (galleryButton) galleryButton.addEventListener("click", function () { openPicker(false); });
      if (removeButton) removeButton.addEventListener("click", function () { resetRow(row); });

      if (input) {
        input.addEventListener("change", function () {
          const file = input.files && input.files[0];
          revokePreview(preview);

          if (!file) {
            resetRow(row);
            return;
          }

          if (filename) filename.textContent = file.name;
          row.classList.add("has-photo");
          if (preview) {
            const objectUrl = URL.createObjectURL(file);
            preview.dataset.objectUrl = objectUrl;
            preview.src = objectUrl;
            preview.hidden = false;
          }
          refreshStatus();
        });
      }
    }

    function addRow() {
      if (allRows().length >= maximumNew) return;
      const html = template.innerHTML.split("__INDEX__").join(String(nextIndex));
      rows.insertAdjacentHTML("beforeend", html);
      nextIndex += 1;
      bindRow(rows.lastElementChild);
      refreshStatus();
    }

    if (addButton) addButton.addEventListener("click", addRow);
    if (maximumNew > 0) addRow();

    form.addEventListener("submit", function (event) {
      if (event.submitter && event.submitter.matches("[data-existing-photo-delete]")) return;
      allRows().forEach(function (row) {
        revokePreview(row.querySelector("[data-photo-preview]"));
      });
      if (!submitButton) return;
      submitButton.disabled = true;
      const label = submitButton.querySelector("span");
      if (label) label.textContent = form.dataset.sendingLabel || "Sending…";
      else submitButton.textContent = form.dataset.sendingLabel || "Sending…";
    });
  }

  document.querySelectorAll("[data-existing-photo-delete]").forEach(confirmExistingPhotoDelete);
  document.querySelectorAll("form[data-contractor-delivery]").forEach(initialiseDelivery);
})();
