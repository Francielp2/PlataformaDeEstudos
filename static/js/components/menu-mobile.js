// Fecha o menu lateral do celular (offcanvas) ao escolher uma página.

export function iniciarMenuMobile() {
    const menu = document.getElementById("menuMobile");
    if (!menu || !window.bootstrap) {
        return;
    }
    menu.querySelectorAll("a.menu-link").forEach(function (link) {
        link.addEventListener("click", function () {
            const instancia = window.bootstrap.Offcanvas.getInstance(menu);
            if (instancia) {
                instancia.hide();
            }
        });
    });
}
