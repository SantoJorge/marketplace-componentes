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


    // ==========================================================
    // FASE 3.1 - MODAL DE SOLICITUD DE VENDEDOR
    // Reutiliza el formulario y la vista Django existentes.
    // ==========================================================

    (function () {
        "use strict";

        const MODAL_ID = "mc-seller-dialog";
        const STYLE_ID = "mc-seller-dialog-css";

        function esRutaVendedor(pathname) {
            return /\/ser-vendedor\/?$/.test(pathname);
        }


        function prepararModal(modal) {
            "use strict";

            if (!modal || modal.dataset.mcInitialized === "1") {
                return;
            }

            modal.dataset.mcInitialized = "1";

            modal.addEventListener("close", function () {

                if (modal.dataset.mcInjected === "1") {
                    modal.remove();
                }
                else if (esRutaVendedor(window.location.pathname)) {
                    window.location.assign(
                        modal.dataset.cancelUrl || "/"
                    );
                }

            });

            // El atributo open permite mostrar el formulario
            // aun cuando JavaScript no funcione.
            //
            // Para convertirlo en un modal verdadero,
            // primero retiramos el atributo open.

            if (modal.hasAttribute("open")) {
                modal.removeAttribute("open");
            }

            if (typeof modal.showModal === "function") {

                try {
                    modal.showModal();
                }
                catch (error) {
                    console.error(
                        "Error al abrir el formulario de vendedor:",
                        error
                    );

                    // Mostrar el formulario aunque falle showModal.
                    modal.setAttribute("open", "");
                }

            }
            else {
                modal.setAttribute("open", "");
            }
        }



        function instalarModal(documento, inyectado) {
            const original = documento.getElementById(MODAL_ID);

            if (!original) {
                return false;
            }

            const estilos = documento.getElementById(STYLE_ID);

            if (estilos && !document.getElementById(STYLE_ID)) {
                document.head.appendChild(
                    document.importNode(estilos, true)
                );
            }

            const anterior = document.getElementById(MODAL_ID);

            if (anterior) {
                anterior.remove();
            }

            const nuevo = document.importNode(original, true);

            if (inyectado) {
                nuevo.dataset.mcInjected = "1";
            }

            document.body.appendChild(nuevo);
            prepararModal(nuevo);

            return true;
        }

        function leerHTML(texto) {
            return new DOMParser().parseFromString(
                texto,
                "text/html"
            );
        }

        // Abrir al visitar directamente /ser-vendedor/.
        function iniciarModalDirecto() {
            const modal = document.getElementById(MODAL_ID);

            if (modal) {
                prepararModal(modal);
            }
        }

        if (document.readyState === "loading") {
            document.addEventListener(
                "DOMContentLoaded",
                iniciarModalDirecto
            );
        } else {
            iniciarModalDirecto();
        }

        // Interceptar solo enlaces de solicitud de vendedor.
        document.addEventListener("click", async function (evento) {

            const cerrar = evento.target.closest(
                "[data-mc-seller-close]"
            );

            if (cerrar) {
                evento.preventDefault();

                const modal = cerrar.closest("dialog");

                if (modal) {
                    modal.close();
                }
                return;
            }

            const enlace = evento.target.closest("a[href]");

            if (!enlace || evento.defaultPrevented) {
                return;
            }

            if (
                evento.button !== 0 ||
                evento.ctrlKey ||
                evento.metaKey ||
                evento.shiftKey ||
                evento.altKey ||
                enlace.hasAttribute("download") ||
                (enlace.target && enlace.target !== "_self")
            ) {
                return;
            }

            const destino = new URL(
                enlace.href,
                window.location.href
            );

            if (
                destino.origin !== window.location.origin ||
                !esRutaVendedor(destino.pathname)
            ) {
                return;
            }

            evento.preventDefault();

            try {
                const respuesta = await fetch(destino.href, {
                    method: "GET",
                    credentials: "same-origin",
                    headers: {
                        "Accept": "text/html"
                    }
                });

                if (!respuesta.ok) {
                    window.location.assign(destino.href);
                    return;
                }

                const documento = leerHTML(
                    await respuesta.text()
                );

                if (!instalarModal(documento, true)) {
                    window.location.assign(destino.href);
                }

            } catch (error) {
                console.error("Modal de vendedor:", error);
                window.location.assign(destino.href);
            }
        });

        // Enviar usando el mismo POST de Django.
        document.addEventListener("submit", async function (evento) {

            const formulario = evento.target;

            if (
                !(formulario instanceof HTMLFormElement) ||
                !formulario.matches("[data-mc-seller-form]")
            ) {
                return;
            }

            evento.preventDefault();

            if (formulario.dataset.mcSending === "1") {
                return;
            }

            formulario.dataset.mcSending = "1";

            const modalActual = formulario.closest("dialog");
            const eraInyectado = Boolean(
                modalActual &&
                modalActual.dataset.mcInjected === "1"
            );

            const boton = formulario.querySelector(
                'button[type="submit"]'
            );

            if (boton) {
                boton.disabled = true;
            }

            try {
                const respuesta = await fetch(formulario.action, {
                    method: "POST",
                    body: new FormData(formulario),
                    credentials: "same-origin",
                    headers: {
                        "Accept": "text/html",
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                const documento = leerHTML(
                    await respuesta.text()
                );

                if (!respuesta.ok ||
                    !instalarModal(documento, eraInyectado)) {

                    window.location.assign(
                        respuesta.url || formulario.action
                    );
                    return;
                }

            } catch (error) {
                console.error("Solicitud de vendedor:", error);

                const aviso = formulario.querySelector(
                    "#mc-seller-network-error"
                );

                if (aviso) {
                    aviso.textContent =
                        "No se pudo confirmar el envío. " +
                        "Comprueba tu conexión e inténtalo nuevamente.";
                }

            } finally {
                delete formulario.dataset.mcSending;

                if (boton) {
                    boton.disabled = false;
                }
            }
        });

    })();


});