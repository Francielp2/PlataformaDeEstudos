// Cronômetro regressivo do simulado. Mostra mm:ss e avisa por leitor de tela
// quando faltam 5 e 1 minuto (o servidor continua sendo quem encerra a tentativa).

import { anunciar } from "../../core/anuncio.js";

const elemento = document.getElementById("tempo-restante");
if (elemento) {
    const texto = elemento.querySelector("[data-tempo]") || elemento;
    let restante = Number(elemento.dataset.restante || 0);
    const avisos = {300: "Faltam 5 minutos para o fim do simulado.", 60: "Falta 1 minuto para o fim do simulado."};

    function desenhar() {
        const horas = Math.floor(restante / 3600);
        const minutos = Math.floor((restante % 3600) / 60);
        const segundos = String(restante % 60).padStart(2, "0");
        texto.textContent = (horas ? horas + ":" + String(minutos).padStart(2, "0") : minutos) + ":" + segundos;
        elemento.classList.toggle("acabando", restante <= 300);
        if (avisos[restante]) {
            anunciar(avisos[restante]);
        }
        if (restante > 0) {
            restante -= 1;
        }
    }
    desenhar();
    window.setInterval(desenhar, 1000);
}
