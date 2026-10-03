// Confirmação amigável antes de ações destrutivas ou de status.
// Uso: <form data-confirmar="Mensagem" data-confirmar-acao="Excluir" data-confirmar-tom="perigo">.

let dialogo = null;

function criarDialogo() {
    dialogo = document.createElement("dialog");
    dialogo.className = "dialogo";
    dialogo.setAttribute("aria-labelledby", "dialogo-titulo");
    dialogo.setAttribute("aria-describedby", "dialogo-texto");
    dialogo.innerHTML =
        '<div class="dialogo-corpo">' +
        '<span class="dialogo-icone" aria-hidden="true"><i class="bi bi-exclamation-lg"></i></span>' +
        '<div><h2 id="dialogo-titulo">Confirmar ação</h2><p id="dialogo-texto"></p></div>' +
        "</div>" +
        '<div class="dialogo-acoes">' +
        '<button type="button" class="btn btn-outline-secondary" data-dialogo-cancelar>Cancelar</button>' +
        '<button type="button" class="btn btn-primary" data-dialogo-confirmar>Confirmar</button>' +
        "</div>";
    document.body.appendChild(dialogo);
    dialogo.querySelector("[data-dialogo-cancelar]").addEventListener("click", function () {
        dialogo.close("cancelar");
    });
    return dialogo;
}

function confirmar(formulario) {
    const caixa = dialogo || criarDialogo();
    const perigo = formulario.dataset.confirmarTom === "perigo";
    caixa.querySelector("#dialogo-texto").textContent = formulario.dataset.confirmar;
    caixa.querySelector("#dialogo-titulo").textContent = formulario.dataset.confirmarTitulo || "Confirmar ação";
    const botao = caixa.querySelector("[data-dialogo-confirmar]");
    botao.textContent = formulario.dataset.confirmarAcao || "Confirmar";
    botao.className = perigo ? "btn btn-danger" : "btn btn-primary";
    caixa.querySelector(".dialogo-icone").className = "dialogo-icone " + (perigo ? "tom-coral" : "tom-sol");
    return new Promise(function (resolver) {
        function aoConfirmar() {
            caixa.close("confirmar");
        }
        botao.addEventListener("click", aoConfirmar, {once: true});
        caixa.addEventListener("close", function () {
            botao.removeEventListener("click", aoConfirmar);
            resolver(caixa.returnValue === "confirmar");
        }, {once: true});
        caixa.showModal();
        caixa.querySelector("[data-dialogo-cancelar]").focus();
    });
}

export function iniciarConfirmacoes() {
    if (typeof HTMLDialogElement === "undefined") {
        return;
    }
    document.addEventListener("submit", function (evento) {
        const formulario = evento.target;
        if (!(formulario instanceof HTMLFormElement) || !formulario.dataset.confirmar) {
            return;
        }
        if (formulario.dataset.confirmado === "1") {
            delete formulario.dataset.confirmado;
            return;
        }
        evento.preventDefault();
        evento.stopImmediatePropagation();
        const enviador = evento.submitter;
        confirmar(formulario).then(function (ok) {
            if (ok) {
                formulario.dataset.confirmado = "1";
                formulario.requestSubmit(enviador || undefined);
            }
        });
    }, true);
}
