// Região viva (aria-live) para anunciar mudanças feitas sem recarregar a página.

let regiao = null;

export function anunciar(mensagem) {
    if (!regiao) {
        regiao = document.getElementById("anuncios");
    }
    if (!regiao) {
        return;
    }
    regiao.textContent = "";
    window.setTimeout(function () {
        regiao.textContent = mensagem;
    }, 60);
}
