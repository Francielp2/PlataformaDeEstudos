// Formulários: evita envio duplo, leva o foco ao resumo de erros e permite
// mostrar/ocultar senha. Não desabilita botões, para preservar o valor do
// botão clicado (ex.: "acao" nos simulados).

export function iniciarFormularios() {
    const resumo = document.querySelector(".resumo-erros");
    if (resumo) {
        resumo.setAttribute("tabindex", "-1");
        resumo.focus({preventScroll: false});
    }

    document.addEventListener("submit", function (evento) {
        const formulario = evento.target;
        if (!(formulario instanceof HTMLFormElement) || evento.defaultPrevented || formulario.method.toLowerCase() !== "post" || formulario.dataset.alternar) {
            return;
        }
        if (formulario.dataset.enviando === "1") {
            evento.preventDefault();
            return;
        }
        formulario.dataset.enviando = "1";
        formulario.setAttribute("aria-busy", "true");
        // Se a navegação não acontecer (ex.: download), libera de novo.
        window.setTimeout(function () {
            delete formulario.dataset.enviando;
            formulario.removeAttribute("aria-busy");
        }, 8000);
    });

    // Voltar pelo navegador pode restaurar a página do cache com o formulário travado.
    window.addEventListener("pageshow", function () {
        document.querySelectorAll("form[data-enviando]").forEach(function (formulario) {
            delete formulario.dataset.enviando;
            formulario.removeAttribute("aria-busy");
        });
    });

    document.querySelectorAll("[data-mostrar-senha]").forEach(function (botao) {
        const campo = document.getElementById(botao.dataset.mostrarSenha);
        if (!campo) {
            return;
        }
        botao.hidden = false;
        botao.addEventListener("click", function () {
            const mostrar = campo.type === "password";
            campo.type = mostrar ? "text" : "password";
            botao.setAttribute("aria-pressed", String(mostrar));
            botao.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
            botao.querySelector("i").className = mostrar ? "bi bi-eye-slash" : "bi bi-eye";
        });
    });
}
