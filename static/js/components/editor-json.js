// Numeração de linhas para os campos de colar JSON das importações.

export function iniciarEditoresJson() {
    document.querySelectorAll("textarea[data-editor-json], .campo-json textarea").forEach(function (campo) {
        const moldura = document.createElement("div");
        moldura.className = "editor-json";
        const linhas = document.createElement("pre");
        linhas.className = "editor-json-linhas";
        linhas.setAttribute("aria-hidden", "true");
        campo.parentNode.insertBefore(moldura, campo);
        moldura.append(linhas, campo);

        function atualizar() {
            const total = Math.max(campo.value.split("\n").length, 12);
            let texto = "";
            for (let i = 1; i <= total; i++) {
                texto += i + "\n";
            }
            linhas.textContent = texto;
            linhas.scrollTop = campo.scrollTop;
        }
        campo.addEventListener("input", atualizar);
        campo.addEventListener("scroll", function () {
            linhas.scrollTop = campo.scrollTop;
        });
        campo.addEventListener("keydown", function (evento) {
            // Tab insere dois espaços; Esc + Tab continua saindo do campo pelo teclado.
            if (evento.key === "Tab" && !evento.shiftKey && campo.dataset.tabLivre !== "1") {
                evento.preventDefault();
                const inicio = campo.selectionStart;
                campo.setRangeText("  ", inicio, campo.selectionEnd, "end");
                atualizar();
            } else if (evento.key === "Escape") {
                campo.dataset.tabLivre = "1";
            }
        });
        campo.addEventListener("blur", function () {
            delete campo.dataset.tabLivre;
        });
        atualizar();
    });
}
