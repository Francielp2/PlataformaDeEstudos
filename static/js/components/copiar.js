// Copiar com um clique: [data-copiar="texto"] ou [data-copiar-de="#id"].

import { anunciar } from "../core/anuncio.js";

function copiarTexto(texto) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(texto);
    }
    return new Promise(function (resolver, rejeitar) {
        const area = document.createElement("textarea");
        area.value = texto;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try {
            document.execCommand("copy") ? resolver() : rejeitar();
        } catch (erro) {
            rejeitar(erro);
        } finally {
            area.remove();
        }
    });
}

export function iniciarCopiar() {
    document.addEventListener("click", function (evento) {
        const botao = evento.target.closest("[data-copiar], [data-copiar-de]");
        if (!botao) {
            return;
        }
        let texto = botao.dataset.copiar;
        if (botao.dataset.copiarDe) {
            const origem = document.querySelector(botao.dataset.copiarDe);
            texto = origem ? origem.textContent : "";
        }
        copiarTexto(texto || "").then(function () {
            botao.classList.add("copiado");
            const icone = botao.querySelector("i");
            const original = icone ? icone.className : "";
            if (icone) {
                icone.className = "bi bi-check2";
            }
            anunciar("Copiado: " + (texto.length > 60 ? "exemplo" : texto));
            window.setTimeout(function () {
                botao.classList.remove("copiado");
                if (icone) {
                    icone.className = original;
                }
            }, 1600);
        }).catch(function () {
            anunciar("Não foi possível copiar. Selecione o texto e copie manualmente.");
        });
    });
}
