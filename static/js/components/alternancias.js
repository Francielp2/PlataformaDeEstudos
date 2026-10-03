// "Estudado" e "Minha lista" com retorno imediato: o botão muda na hora e o
// pedido vai em segundo plano. Sem JS, o formulário é enviado normalmente.
// O formulário declara os dois estados em data-*: rotulo, ícone, classe e título.

import { anunciar } from "../core/anuncio.js";

function aplicarEstado(formulario, ligado) {
    const botao = formulario.querySelector("button[type=submit]");
    const sufixo = ligado ? "Ligado" : "Desligado";
    const rotulo = formulario.dataset["rotulo" + sufixo];
    const icone = formulario.dataset["icone" + sufixo];
    botao.className = formulario.dataset["classe" + sufixo];
    botao.title = formulario.dataset["titulo" + sufixo] || "";
    botao.setAttribute("aria-pressed", String(ligado));
    botao.innerHTML = '<i class="bi ' + icone + '" aria-hidden="true"></i> <span></span>';
    botao.querySelector("span").textContent = rotulo;
    formulario.dataset.ligado = String(ligado);
    const cartao = formulario.closest("[data-cartao-estudado]");
    if (cartao && formulario.dataset.alternar === "estudado") {
        cartao.classList.toggle("esta-estudado", ligado);
    }
}

export function iniciarAlternancias() {
    document.addEventListener("submit", function (evento) {
        const formulario = evento.target;
        if (!(formulario instanceof HTMLFormElement) || !formulario.dataset.alternar || formulario.dataset.ocupado === "1") {
            return;
        }
        evento.preventDefault();
        const estavaLigado = formulario.dataset.ligado === "true";
        formulario.dataset.ocupado = "1";
        aplicarEstado(formulario, !estavaLigado);
        fetch(formulario.action, {
            method: "POST",
            body: new FormData(formulario),
            credentials: "same-origin",
            headers: {"X-Requested-With": "fetch"},
        }).then(function (resposta) {
            if (!resposta.ok) {
                throw new Error("falha");
            }
            anunciar(formulario.dataset[!estavaLigado ? "anuncioLigado" : "anuncioDesligado"] || "Alteração salva.");
        }).catch(function () {
            aplicarEstado(formulario, estavaLigado);
            anunciar("Não foi possível salvar agora. Tente novamente.");
        }).finally(function () {
            delete formulario.dataset.ocupado;
        });
    });
}
