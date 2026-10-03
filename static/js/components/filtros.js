// Filtros que se aplicam ao mudar um select. Sem JS, o botão "Filtrar" continua
// funcionando; a busca por texto é aplicada com Enter.

export function iniciarFiltros() {
    document.querySelectorAll("form[data-filtro-automatico]").forEach(function (formulario) {
        formulario.querySelectorAll("select").forEach(function (campo) {
            campo.addEventListener("change", function () {
                formulario.classList.add("carregando");
                formulario.requestSubmit();
            });
        });
    });
}
