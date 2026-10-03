// Prévia somente leitura dos dados do vídeo no cadastro (o servidor consulta o
// YouTube de novo ao salvar). Texto inserido com textContent, nunca como HTML.

const botao = document.getElementById("buscarDadosVideo");
const campo = botao && document.getElementById(botao.dataset.campo);
const destino = document.getElementById("previewVideo");

function texto(tag, conteudo, classe) {
    const elemento = document.createElement(tag);
    elemento.textContent = conteudo;
    if (classe) {
        elemento.className = classe;
    }
    return elemento;
}

function aviso(mensagem) {
    const caixa = document.createElement("div");
    caixa.className = "aviso tom-sol";
    caixa.innerHTML = '<i class="bi bi-exclamation-triangle" aria-hidden="true"></i>';
    caixa.appendChild(texto("p", mensagem));
    destino.replaceChildren(caixa);
}

if (botao && campo && destino) {
    botao.hidden = false;
    botao.addEventListener("click", function () {
        if (!campo.value.trim()) {
            aviso("Cole o link do vídeo primeiro.");
            campo.focus();
            return;
        }
        destino.replaceChildren(texto("span", "Consultando o YouTube…", "texto-suave small"));
        fetch(botao.dataset.urlPreview + "?url=" + encodeURIComponent(campo.value), {credentials: "same-origin"})
            .then(function (resposta) { return resposta.json(); })
            .then(function (dados) {
                if (!dados.ok) {
                    aviso(dados.erro);
                    return;
                }
                const cartao = document.createElement("div");
                cartao.className = "previa-video";
                const imagem = document.createElement("img");
                imagem.src = dados.thumbnail_url;
                imagem.alt = "";
                imagem.width = 160;
                imagem.height = 90;
                const info = document.createElement("div");
                info.append(texto("strong", dados.titulo, "d-block"));
                const linha = texto("span", "Canal: ", "small");
                const canal = document.createElement("a");
                canal.href = dados.canal_url;
                canal.target = "_blank";
                canal.rel = "noopener";
                canal.textContent = dados.canal_nome;
                linha.append(canal);
                info.append(linha);
                cartao.append(imagem, info);
                destino.replaceChildren(cartao);
            })
            .catch(function () {
                aviso("Não foi possível consultar o YouTube agora.");
            });
    });
}
