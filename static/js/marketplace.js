// =========================================================
// MARKETPLACE COMPONENTES
// JAVASCRIPT PRINCIPAL
// =========================================================


// ---------------------------------------------------------
// CONFIRMACIÓN DE CARGA
// ---------------------------------------------------------

console.log("Marketplace público cargado correctamente.");


// ---------------------------------------------------------
// MOSTRAR / OCULTAR CONTRASEÑAS
// ---------------------------------------------------------

document.addEventListener("click", function (event) {

    const button = event.target.closest(
        "[data-toggle-password]"
    );

    if (!button) {
        return;
    }


    const targetId =
        button.dataset.togglePassword;


    const input =
        document.getElementById(targetId);


    if (!input) {
        return;
    }


    if (input.type === "password") {

        input.type = "text";

        button.textContent = "🙈";

        button.setAttribute(
            "aria-label",
            "Ocultar contraseña"
        );

    } else {

        input.type = "password";

        button.textContent = "👁";

        button.setAttribute(
            "aria-label",
            "Mostrar contraseña"
        );

    }

});