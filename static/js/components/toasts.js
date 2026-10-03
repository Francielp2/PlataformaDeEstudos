// Mensagens do sistema: botão fechar e saída automática só para mensagens de
// sucesso/informação (pausa enquanto o cursor ou o foco estão nelas).

const TEMPO_VISIVEL = 7000;

function fechar(toast) {
    toast.classList.add("saindo");
    window.setTimeout(function () {
        toast.remove();
    }, 220);
}

export function iniciarToasts() {
    document.querySelectorAll(".toast-msg").forEach(function (toast) {
        const botao = toast.querySelector(".toast-fechar");
        if (botao) {
            botao.addEventListener("click", function () {
                fechar(toast);
            });
        }
        if (toast.dataset.autoFechar !== "true") {
            return;
        }
        let restante = TEMPO_VISIVEL;
        let inicio = Date.now();
        let temporizador = window.setTimeout(function () { fechar(toast); }, restante);
        function pausar() {
            window.clearTimeout(temporizador);
            restante -= Date.now() - inicio;
        }
        function retomar() {
            inicio = Date.now();
            temporizador = window.setTimeout(function () { fechar(toast); }, Math.max(restante, 1500));
        }
        toast.addEventListener("mouseenter", pausar);
        toast.addEventListener("mouseleave", retomar);
        toast.addEventListener("focusin", pausar);
        toast.addEventListener("focusout", retomar);
    });
}
