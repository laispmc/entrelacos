// EntreLaços — interações no navegador.
// Tudo aqui é melhoria de uso: as validações reais acontecem no servidor.
(function () {
  "use strict";

  // Botões − / + dos seletores de quantidade
  document.querySelectorAll(".seletor-qtd").forEach(function (seletor) {
    var campo = seletor.querySelector("input");
    var maximo = parseInt(seletor.dataset.max, 10);
    var minimo = parseInt(campo.min || "0", 10);
    var envioAutomatico = seletor.hasAttribute("data-auto");
    var temporizador;

    function ajustar(valor) {
      if (isNaN(valor)) valor = minimo;
      if (!isNaN(maximo)) valor = Math.min(valor, maximo);
      campo.value = Math.max(valor, minimo);
    }

    function agendarEnvio() {
      if (!envioAutomatico) return;
      clearTimeout(temporizador);
      temporizador = setTimeout(function () { seletor.closest("form").submit(); }, 600);
    }

    seletor.querySelectorAll("button[data-passo]").forEach(function (botao) {
      botao.addEventListener("click", function () {
        ajustar(parseInt(campo.value, 10) + parseInt(botao.dataset.passo, 10));
        agendarEnvio();
      });
    });
    campo.addEventListener("change", function () {
      ajustar(parseInt(campo.value, 10));
      agendarEnvio();
    });
  });

  // Máscara de telefone: (27) 99999-1234
  document.querySelectorAll("[data-mascara='telefone']").forEach(function (campo) {
    campo.addEventListener("input", function () {
      var d = campo.value.replace(/\D/g, "").slice(0, 11);
      var saida = d;
      if (d.length > 2) saida = "(" + d.slice(0, 2) + ") " + d.slice(2);
      if (d.length > 6) {
        var corte = d.length === 11 ? 7 : 6;
        saida = "(" + d.slice(0, 2) + ") " + d.slice(2, corte) + "-" + d.slice(corte);
      }
      campo.value = saida;
    });
  });

  // Pesquisa: troca rótulo e máscara conforme "Nome" ou "Telefone"
  var rotuloBusca = document.querySelector("[data-rotulo-busca]");
  if (rotuloBusca) {
    var campoBusca = document.getElementById(rotuloBusca.getAttribute("for"));
    var atualizarBusca = function () {
      var marcado = document.querySelector("input[name='tipo']:checked");
      var porTelefone = marcado && marcado.value === "telefone";
      rotuloBusca.textContent = porTelefone ? "Telefone usado na doação" : "Nome do doador";
      campoBusca.placeholder = porTelefone ? "(27) 99999-1234" : "Digite ao menos 3 letras";
      campoBusca.inputMode = porTelefone ? "tel" : "text";
      campoBusca.type = porTelefone ? "password" : "text";
    };
    document.querySelectorAll("input[name='tipo']").forEach(function (r) {
      r.addEventListener("change", function () { campoBusca.value = ""; atualizarBusca(); });
    });
    atualizarBusca();
  }

  // Prévia da imagem de capa antes do envio
  document.querySelectorAll("input[type='file'][data-previa]").forEach(function (campo) {
    var previa = document.getElementById(campo.dataset.previa);
    campo.addEventListener("change", function () {
      var arquivo = campo.files && campo.files[0];
      if (!arquivo || !previa) return;
      previa.src = URL.createObjectURL(arquivo);
      previa.hidden = false;
    });
  });

  // Checklist: botão "tudo" e limite recebido + cancelado <= pendente
  document.querySelectorAll("[data-preencher]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var campo = document.querySelector("[name='" + botao.dataset.preencher + "']");
      var grupo = document.querySelectorAll("[data-grupo='" + campo.dataset.grupo + "']");
      grupo.forEach(function (c) { c.value = 0; });
      campo.value = botao.dataset.valor;
    });
  });

  // Confirmação antes de ações sensíveis
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirmar)) e.preventDefault();
    });
  });

  // Evita duplo envio: desabilita o botão depois do primeiro clique
  document.querySelectorAll("button[data-enviando]").forEach(function (botao) {
    botao.form && botao.form.addEventListener("submit", function () {
      setTimeout(function () {
        botao.disabled = true;
        botao.textContent = botao.dataset.enviando;
      }, 0);
    });
  });
})();
