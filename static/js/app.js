// Ponto de entrada do JavaScript (módulo ES, sem build). Comportamentos de
// página ficam em js/pages/<app>/ e entram pelo bloco extra_js.

import { iniciarPreferencias } from "./core/preferencias.js";
import { iniciarToasts } from "./components/toasts.js";
import { iniciarFiltros } from "./components/filtros.js";
import { iniciarConfirmacoes } from "./components/confirmacao.js";
import { iniciarAlternancias } from "./components/alternancias.js";
import { iniciarPaleta } from "./components/paleta.js";
import { iniciarCopiar } from "./components/copiar.js";
import { iniciarFormularios } from "./components/formularios.js";
import { iniciarEditoresJson } from "./components/editor-json.js";
import { iniciarMenuMobile } from "./components/menu-mobile.js";

[
    iniciarPreferencias,
    iniciarToasts,
    iniciarFiltros,
    iniciarConfirmacoes,
    iniciarAlternancias,
    iniciarPaleta,
    iniciarCopiar,
    iniciarFormularios,
    iniciarEditoresJson,
    iniciarMenuMobile,
].forEach(function (iniciar) {
    try {
        iniciar();
    } catch (erro) {
        // Um componente com problema não pode impedir os outros de funcionar.
        console.error(erro);
    }
});
