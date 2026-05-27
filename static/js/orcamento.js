(function () {
  "use strict";

  var tbody = document.getElementById("items-body");
  var grandTotalEl = document.getElementById("grand-total");
  var formMessage = document.getElementById("form-message");
  var itemCounter = 0;

  function addItemRow() {
    itemCounter++;
    var row = document.createElement("tr");
    row.innerHTML =
      '<td><input type="text" class="inp-item" placeholder="1" maxlength="10"></td>' +
      '<td><input type="text" class="inp-desc" placeholder="Descricao do servico/material"></td>' +
      '<td><input type="number" class="inp-qtd" value="1" min="1" step="1"></td>' +
      '<td><input type="number" class="inp-vu" value="0.00" min="0" step="0.01"></td>' +
      '<td><span class="vt-readonly">R$ 0,00</span></td>' +
      '<td><button type="button" class="btn-remove-item" title="Remover">&times;</button></td>';
    tbody.appendChild(row);

    var qtdInput = row.querySelector(".inp-qtd");
    var vuInput = row.querySelector(".inp-vu");
    var vtSpan = row.querySelector(".vt-readonly");

    function recalc() {
      var q = parseFloat(qtdInput.value) || 0;
      var vu = parseFloat(vuInput.value) || 0;
      vtSpan.textContent = "R$ " + (q * vu).toFixed(2).replace(".", ",");
      recalcGrandTotal();
    }

    qtdInput.addEventListener("input", recalc);
    vuInput.addEventListener("input", recalc);
    row.querySelector(".btn-remove-item").addEventListener("click", function () {
      row.remove();
      recalcGrandTotal();
      if (tbody.children.length === 0) addItemRow();
    });
    recalc();
  }

  function recalcGrandTotal() {
    var total = 0;
    tbody.querySelectorAll("tr").forEach(function (row) {
      var q = parseFloat(row.querySelector(".inp-qtd").value) || 0;
      var vu = parseFloat(row.querySelector(".inp-vu").value) || 0;
      total += q * vu;
    });
    grandTotalEl.textContent = "R$ " + total.toFixed(2).replace(".", ",");
  }

  function collectFormData() {
    var itens = [];
    tbody.querySelectorAll("tr").forEach(function (row) {
      var desc = row.querySelector(".inp-desc").value.trim();
      var qtd = parseInt(row.querySelector(".inp-qtd").value) || 0;
      var vu = parseFloat(row.querySelector(".inp-vu").value) || 0;
      if (desc && qtd > 0) {
        itens.push({
          item: row.querySelector(".inp-item").value.trim() || "",
          descricao: desc,
          quantidade: qtd,
          valor_unitario: vu,
        });
      }
    });
    return itens;
  }

  function showMessage(msg, type) {
    formMessage.style.display = "block";
    formMessage.className = "form-message " + type;
    formMessage.textContent = msg;
    setTimeout(function () { formMessage.style.display = "none"; }, 5000);
  }

  function hideMessage() {
    formMessage.style.display = "none";
  }

  // ---------- SUBMISSAO ----------
  document.getElementById("btn-add-item").addEventListener("click", addItemRow);

  document.getElementById("form-orcamento").addEventListener("submit", function (e) {
    e.preventDefault();
    hideMessage();

    var btn = document.getElementById("btn-gerar");

    var itens = collectFormData();
    if (itens.length === 0) {
      showMessage("Adicione pelo menos um item com descricao e quantidade.", "error");
      return;
    }

    var payload = {
      nome: document.getElementById("nome").value.trim(),
      empresa: document.getElementById("empresa").value.trim(),
      telefone: document.getElementById("telefone").value.trim(),
      endereco: document.getElementById("endereco").value.trim(),
      cidade: document.getElementById("cidade").value.trim(),
      validade_dias: parseInt(document.getElementById("validade_dias").value) || 15,
      observacoes: document.getElementById("observacoes").value.trim(),
      itens: itens,
    };

    if (!payload.nome || !payload.telefone || !payload.endereco || !payload.cidade) {
      showMessage("Preencha todos os campos obrigatorios do cliente.", "error");
      return;
    }

    btn.disabled = true;
    btn.textContent = "Gerando PDF...";

    fetch("/api/orcamentos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        if (!r.ok) {
          // Tenta extrair erro como JSON; se falhar, devolve o status HTTP
          var ct = r.headers.get("Content-Type") || "";
          if (ct.indexOf("application/json") !== -1) {
            return r.json().then(function (d) { throw new Error(d.error || "Erro " + r.status); });
          }
          throw new Error("Erro do servidor (HTTP " + r.status + "). Tente novamente.");
        }
        return r.json();
      })
      .then(function (data) {
        // Mostrar modal
        document.getElementById("modal-hash-id").textContent = data.hash_id;
        document.getElementById("link-download-pdf").href = "/pdf/" + data.hash_id;
        document.getElementById("modal-sucesso").style.display = "flex";

        // Baixar o PDF: abre em nova aba, o Content-Disposition: attachment faz o browser baixar
        window.open("/pdf/" + data.hash_id, "_blank");
      })
      .catch(function (err) {
        showMessage(err.message || "Erro de conexao. Verifique o servidor.", "error");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Gerar e Enviar Orcamento PDF";
      });
  });

  // ---------- INICIA COM 1 LINHA ----------
  addItemRow();
})();
