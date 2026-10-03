// Formulário de questão: adicionar alternativas (formset) e filtrar a lista de
// conteúdos. Sem JS, o formulário continua enviando os mesmos campos.

const botao = document.getElementById("adicionar-alternativa");
const lista = document.getElementById("alternativas-container");
const modelo = document.getElementById("alternativa-empty-template");
const total = document.querySelector("input[name$='-TOTAL_FORMS']");

if (botao && lista && modelo && total) {
    botao.hidden = false;
    botao.addEventListener("click", function () {
        const indice = Number(total.value);
        lista.insertAdjacentHTML("beforeend", modelo.innerHTML.replace(/__prefix__/g, indice));
        total.value = indice + 1;
        const novo = lista.lastElementChild;
        const campo = novo && novo.querySelector("input[type=text], textarea");
        if (campo) {
            campo.focus();
        }
    });
}

document.querySelectorAll("[data-lista-filtravel]").forEach(function (caixa) {
    const filtro = caixa.querySelector(".lista-escolha-filtro");
    const itens = Array.from(caixa.querySelectorAll(".lista-escolha-item"));
    if (!filtro || itens.length < 8) {
        return;
    }
    filtro.hidden = false;
    filtro.addEventListener("input", function () {
        const termo = filtro.value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
        itens.forEach(function (item) {
            const texto = item.textContent.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
            item.hidden = Boolean(termo) && !texto.includes(termo);
        });
    });
});
