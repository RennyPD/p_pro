// Links to the application and the public plans (prices come from the API, so
// the site never shows outdated prices). No cookies, no third-party scripts.
(function () {
  var config = window.NEXO_SITE || {};
  var app = config.appUrl && config.appUrl.indexOf("__") !== 0 ? config.appUrl : "http://localhost:5173";
  var api = config.apiUrl && config.apiUrl.indexOf("__") !== 0 ? config.apiUrl : "http://localhost:8000";

  var email =
    config.contactEmail && config.contactEmail.indexOf("__") !== 0 ? config.contactEmail : "";
  document.querySelectorAll("[data-contact]").forEach(function (link) {
    if (email) {
      link.setAttribute("href", "mailto:" + email);
      if (link.hasAttribute("data-contact-text")) link.textContent = email;
    }
  });

  document.querySelectorAll("[data-app]").forEach(function (link) {
    link.setAttribute("href", app.replace(/\/$/, "") + link.getAttribute("data-app"));
  });

  var target = document.getElementById("plans");
  if (!target) return;
  var money = function (value, currency) {
    return Number(value).toLocaleString("es-DO", { minimumFractionDigits: 0 }) + " " + currency;
  };
  fetch(api.replace(/\/$/, "") + "/public/signup")
    .then(function (response) {
      if (!response.ok) throw new Error("plans");
      return response.json();
    })
    .then(function (data) {
      target.textContent = "";
      data.plans.forEach(function (plan) {
        var card = document.createElement("article");
        card.className = "card";
        var title = document.createElement("h3");
        title.textContent = plan.name;
        var price = document.createElement("p");
        price.className = "price";
        price.textContent = money(plan.monthly_price, plan.currency) + " ";
        var unit = document.createElement("small");
        unit.textContent = "al mes";
        price.appendChild(unit);
        var detail = document.createElement("p");
        detail.textContent =
          (plan.description ? plan.description + ". " : "") +
          (plan.max_students ? "Hasta " + plan.max_students.toLocaleString("es-DO") + " estudiantes activos." : "Sin límite de estudiantes.");
        var start = document.createElement("a");
        start.className = "button";
        start.href = app.replace(/\/$/, "") + "/registro";
        start.textContent = "Probar " + data.trial_days + " días gratis";
        card.append(title, price, detail, start);
        target.appendChild(card);
      });
      var custom = document.createElement("article");
      custom.className = "card";
      var heading = document.createElement("h3");
      heading.textContent = "Institucional";
      var text = document.createElement("p");
      text.textContent = "Para grupos educativos y universidades grandes: sin límites y condiciones a medida.";
      var contact = document.createElement("a");
      contact.className = "button button--ghost";
      contact.href = "#contacto";
      contact.textContent = "Hablemos";
      custom.append(heading, text, contact);
      target.appendChild(custom);
    })
    .catch(function () {
      target.textContent = "No pudimos cargar los precios en este momento. Escríbenos y te los enviamos.";
    });
})();
