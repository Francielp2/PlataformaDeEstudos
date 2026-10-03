// Busca rápida (Ctrl+K ou "/"): procura entre as páginas do menu e os itens
// marcados com data-paleta-item na página atual. Não consulta o servidor.

function normalizar(texto) {
    return (texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

function coletarItens() {
    const itens = [];
    const vistos = new Set();
    document.querySelectorAll(".sidebar-desktop .menu-link, [data-paleta-item]").forEach(function (elemento) {
        const url = elemento.dataset.paletaUrl || elemento.getAttribute("href");
        const titulo = elemento.dataset.paletaTitulo || elemento.textContent.trim();
        if (!url || vistos.has(url + titulo)) {
            return;
        }
        vistos.add(url + titulo);
        const icone = elemento.dataset.paletaIcone || (elemento.querySelector("i") && elemento.querySelector("i").className) || "bi bi-arrow-right-short";
        itens.push({
            titulo: titulo,
            url: url,
            grupo: elemento.dataset.paletaGrupo || "Páginas",
            detalhe: elemento.dataset.paletaDetalhe || "",
            icone: icone,
            busca: normalizar(titulo + " " + (elemento.dataset.paletaDetalhe || "")),
        });
    });
    return itens;
}

export function iniciarPaleta() {
    const dialogo = document.getElementById("paleta");
    if (!dialogo || typeof dialogo.showModal !== "function") {
        return;
    }
    const campo = dialogo.querySelector("input");
    const lista = dialogo.querySelector(".paleta-lista");
    let itens = [];
    let visiveis = [];
    let selecionado = 0;

    function desenhar() {
        const termo = normalizar(campo.value);
        visiveis = itens.filter(function (item) {
            return !termo || termo.split(/\s+/).every(function (parte) { return item.busca.includes(parte); });
        }).slice(0, 40);
        selecionado = Math.min(selecionado, Math.max(visiveis.length - 1, 0));
        lista.replaceChildren();
        if (!visiveis.length) {
            const vazio = document.createElement("li");
            vazio.className = "paleta-vazio";
            vazio.textContent = "Nada encontrado no menu nem nesta página.";
            lista.appendChild(vazio);
            campo.removeAttribute("aria-activedescendant");
            return;
        }
        let grupoAtual = "";
        visiveis.forEach(function (item, indice) {
            if (item.grupo !== grupoAtual) {
                grupoAtual = item.grupo;
                const titulo = document.createElement("li");
                titulo.className = "paleta-grupo";
                titulo.setAttribute("role", "presentation");
                titulo.textContent = grupoAtual;
                lista.appendChild(titulo);
            }
            const li = document.createElement("li");
            li.className = "paleta-item";
            li.id = "paleta-opcao-" + indice;
            li.setAttribute("role", "option");
            li.setAttribute("aria-selected", String(indice === selecionado));
            const link = document.createElement("a");
            link.href = item.url;
            link.tabIndex = -1;
            const icone = document.createElement("i");
            icone.className = item.icone;
            icone.setAttribute("aria-hidden", "true");
            const texto = document.createElement("span");
            texto.textContent = item.titulo;
            link.append(icone, texto);
            if (item.detalhe) {
                const detalhe = document.createElement("small");
                detalhe.textContent = item.detalhe;
                link.appendChild(detalhe);
            }
            li.appendChild(link);
            lista.appendChild(li);
        });
        campo.setAttribute("aria-activedescendant", "paleta-opcao-" + selecionado);
    }

    function abrir() {
        itens = coletarItens();
        campo.value = "";
        selecionado = 0;
        desenhar();
        dialogo.showModal();
        campo.focus();
    }

    campo.addEventListener("input", function () {
        selecionado = 0;
        desenhar();
    });
    campo.addEventListener("keydown", function (evento) {
        if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
            evento.preventDefault();
            if (!visiveis.length) {
                return;
            }
            selecionado = (selecionado + (evento.key === "ArrowDown" ? 1 : -1) + visiveis.length) % visiveis.length;
            desenhar();
            const atual = document.getElementById("paleta-opcao-" + selecionado);
            if (atual) {
                atual.scrollIntoView({block: "nearest"});
            }
        } else if (evento.key === "Enter" && visiveis[selecionado]) {
            evento.preventDefault();
            window.location.href = visiveis[selecionado].url;
        }
    });
    dialogo.addEventListener("click", function (evento) {
        if (evento.target === dialogo) {
            dialogo.close();
        }
    });
    document.querySelectorAll("[data-abrir-paleta]").forEach(function (botao) {
        botao.addEventListener("click", abrir);
    });
    document.addEventListener("keydown", function (evento) {
        const digitando = evento.target.closest && evento.target.closest("input, textarea, select, [contenteditable]");
        if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === "k") {
            evento.preventDefault();
            if (!dialogo.open) {
                abrir();
            }
        } else if (evento.key === "/" && !digitando && !dialogo.open) {
            evento.preventDefault();
            abrir();
        }
    });
}
