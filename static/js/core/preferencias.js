// Preferências de acessibilidade (tamanho da fonte e alto contraste), salvas no
// navegador. O <head> já aplica o valor salvo antes da primeira pintura.

const CHAVE_FONTE = "pe-fonte";
const CHAVE_CONTRASTE = "pe-contraste";

function ler(chave) {
    try {
        return localStorage.getItem(chave);
    } catch (erro) {
        return null;
    }
}

function salvar(chave, valor) {
    try {
        if (valor) {
            localStorage.setItem(chave, valor);
        } else {
            localStorage.removeItem(chave);
        }
    } catch (erro) {}
}

function aplicar(atributo, valor) {
    if (valor) {
        document.documentElement.setAttribute(atributo, valor);
    } else {
        document.documentElement.removeAttribute(atributo);
    }
}

function marcarBotoes() {
    const fonte = document.documentElement.getAttribute("data-fonte") || "";
    const contraste = document.documentElement.getAttribute("data-contraste") || "";
    document.querySelectorAll("[data-pref-fonte]").forEach(function (botao) {
        botao.setAttribute("aria-pressed", String(botao.dataset.prefFonte === fonte));
    });
    document.querySelectorAll("[data-pref-contraste]").forEach(function (botao) {
        botao.setAttribute("aria-pressed", String(botao.dataset.prefContraste === contraste));
    });
}

export function iniciarPreferencias() {
    document.querySelectorAll("[data-pref-fonte]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            const valor = botao.dataset.prefFonte;
            aplicar("data-fonte", valor);
            salvar(CHAVE_FONTE, valor);
            marcarBotoes();
        });
    });
    document.querySelectorAll("[data-pref-contraste]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            const valor = botao.dataset.prefContraste;
            aplicar("data-contraste", valor);
            salvar(CHAVE_CONTRASTE, valor);
            marcarBotoes();
        });
    });
    marcarBotoes();
    // Mantém as abas abertas em sincronia.
    window.addEventListener("storage", function (evento) {
        if (evento.key === CHAVE_FONTE) {
            aplicar("data-fonte", ler(CHAVE_FONTE));
        } else if (evento.key === CHAVE_CONTRASTE) {
            aplicar("data-contraste", ler(CHAVE_CONTRASTE));
        }
        marcarBotoes();
    });
}
