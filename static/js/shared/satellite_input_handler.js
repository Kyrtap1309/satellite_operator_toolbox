class SatelliteInputHandler {
  constructor(prefix = "") {
    this.prefix = prefix;
    this.noradRadio = document.getElementById(`${prefix}input_norad`);
    this.tleRadio = document.getElementById(`${prefix}input_tle`);
    this.noradInput = document.getElementById(`${prefix}norad_input`);
    this.tleInput = document.getElementById(`${prefix}tle_input`);

    this.init();
  }

  init() {
    if (this.noradRadio && this.tleRadio) {
      this.noradRadio.addEventListener("change", () =>
        this.toggleInputMethod()
      );
      this.tleRadio.addEventListener("change", () => this.toggleInputMethod());
    }
  }

  toggleInputMethod() {
    if (this.noradRadio.checked) {
      this.showNoradInput();
      this.clearTleFields();
    } else {
      this.showTleInput();
      this.clearNoradField();
    }
  }

  showNoradInput() {
    if (this.noradInput && this.tleInput) {
      this.noradInput.style.display = "block";
      this.tleInput.style.display = "none";
    }
  }

  showTleInput() {
    if (this.noradInput && this.tleInput) {
      this.noradInput.style.display = "none";
      this.tleInput.style.display = "block";
    }
  }

  clearTleFields() {
    const fields = [
      `${this.prefix}tle_name`,
      `${this.prefix}tle_line1`,
      `${this.prefix}tle_line2`,
    ];
    fields.forEach((fieldId) => {
      const field = document.getElementById(fieldId);
      if (field) field.value = "";
    });
  }

  clearNoradField() {
    const field = document.getElementById(`${this.prefix}norad_id`);
    if (field) field.value = "";
  }
}

// Auto-initialize if prefix is provided via data attribute
document.addEventListener("DOMContentLoaded", function () {
  const containers = document.querySelectorAll("[data-satellite-input]");
  containers.forEach((container) => {
    const prefix = container.dataset.satelliteInput;
    new SatelliteInputHandler(prefix);
  });
});
