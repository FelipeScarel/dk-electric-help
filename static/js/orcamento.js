(function () {
  "use strict";

  var tbody = document.getElementById("items-body");
  var grandTotalEl = document.getElementById("grand-total");
  var totalMateriaisEl = document.getElementById("total-materiais");
  var totalMaoObraEl = document.getElementById("total-mao-obra");
  var itemCounter = 0;

  // ============================================================
  // TOAST NOTIFICATION
  // ============================================================
  function toast(msg, type) {
    var el = document.getElementById("toast");
    el.textContent = msg;
    el.className = "toast " + (type || "success");
    el.style.display = "flex";
    el.style.animation = "none";
    el.offsetHeight; // reflow
    el.style.animation = "slideUp 0.3s ease";
    clearTimeout(el._timeout);
    el._timeout = setTimeout(function () {
      el.style.animation = "fadeOut 0.3s ease";
      setTimeout(function () { el.style.display = "none"; }, 280);
    }, 4000);
  }

  // ============================================================
  // PHONE MASK
  // ============================================================
  document.getElementById("telefone").addEventListener("input", function (e) {
    var v = e.target.value.replace(/\D/g, "");
    if (v.length > 11) v = v.slice(0, 11);
    if (v.length > 0) v = "(" + v;
    if (v.length > 3) v = v.slice(0, 3) + ") " + v.slice(3);
    if (v.length > 10) v = v.slice(0, 10) + "-" + v.slice(10);
    e.target.value = v;
  });

  // ============================================================
  // CEP AUTOCOMPLETE
  // ============================================================
  var cepTimer = null;
  document.getElementById("cep").addEventListener("input", function (e) {
    var v = e.target.value.replace(/\D/g, "");
    if (v.length > 8) v = v.slice(0, 8);
    if (v.length > 5) v = v.slice(0, 5) + "-" + v.slice(5);
    e.target.value = v;

    var status = document.getElementById("cep-status");
    if (v.replace(/\D/g, "").length === 8) {
      status.textContent = "Buscando...";
      clearTimeout(cepTimer);
      cepTimer = setTimeout(function () {
        fetch("https://viacep.com.br/ws/" + v.replace(/\D/g, "") + "/json/")
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.erro) { status.textContent = "CEP nao encontrado"; return; }
            document.getElementById("endereco").value = data.logradouro || "";
            document.getElementById("bairro").value = data.bairro || "";
            document.getElementById("cidade").value = data.localidade || "";
            document.getElementById("estado").value = data.uf || "";
            status.textContent = data.localidade ? "CEP encontrado: " + data.localidade + "/" + data.uf : "";
            status.style.color = "#2E7D32";
            toast("Endereco preenchido automaticamente", "success");
          })
          .catch(function () { status.textContent = "Erro ao buscar CEP"; });
      }, 600);
    } else if (v.length > 0) {
      status.textContent = v.length < 9 ? "Digite o CEP completo" : "";
    }
  });

  // ============================================================
  // FORMATTER
  // ============================================================
  function formatBRL(val) {
    return "R$ " + val.toFixed(2).replace(".", ",");
  }

  // ============================================================
  // ITEMS TABLE — Material + Mao de Obra split
  // ============================================================
  function addItemRow() {
    itemCounter++;
    var row = document.createElement("tr");
    row.innerHTML =
      '<td><input type="text" class="inp-item" placeholder="#" maxlength="10" aria-label="Numero do item"></td>' +
      '<td><input type="text" class="inp-desc" placeholder="Descricao do servico ou material" aria-label="Descricao"></td>' +
      '<td><input type="number" class="inp-qtd" value="1" min="1" step="1" inputmode="numeric" aria-label="Quantidade"></td>' +
      '<td><input type="number" class="inp-vm" value="0.00" min="0" step="0.01" inputmode="decimal" aria-label="Valor do material unitario"></td>' +
      '<td><input type="number" class="inp-vo" value="0.00" min="0" step="0.01" inputmode="decimal" aria-label="Valor da mao de obra unitario"></td>' +
      '<td><span class="item-total-readonly">' + formatBRL(0) + '</span></td>' +
      '<td><button type="button" class="btn-remove-row" title="Remover item" aria-label="Remover item">&times;</button></td>';
    tbody.appendChild(row);

    var qtdInp = row.querySelector(".inp-qtd");
    var vmInp = row.querySelector(".inp-vm");
    var voInp = row.querySelector(".inp-vo");
    var totalSpan = row.querySelector(".item-total-readonly");

    function recalc() {
      var q = parseFloat(qtdInp.value) || 0;
      var vm = parseFloat(vmInp.value) || 0;
      var vo = parseFloat(voInp.value) || 0;
      // Subtotal = (Valor Material + Valor Mao de Obra) * Quantidade
      totalSpan.textContent = formatBRL((vm + vo) * q);
      recalcGrandTotal();
    }

    qtdInp.addEventListener("input", recalc);
    vmInp.addEventListener("input", recalc);
    voInp.addEventListener("input", recalc);
    row.querySelector(".btn-remove-row").addEventListener("click", function () {
      row.style.opacity = "0";
      row.style.transform = "translateX(-10px)";
      row.style.transition = "all 200ms ease";
      setTimeout(function () {
        row.remove();
        recalcGrandTotal();
        if (tbody.children.length === 0) addItemRow();
      }, 200);
    });
    recalc();
  }

  function recalcGrandTotal() {
    var totalMateriais = 0;
    var totalMaoObra = 0;
    tbody.querySelectorAll("tr").forEach(function (row) {
      var q = parseFloat(row.querySelector(".inp-qtd").value) || 0;
      var vm = parseFloat(row.querySelector(".inp-vm").value) || 0;
      var vo = parseFloat(row.querySelector(".inp-vo").value) || 0;
      totalMateriais += q * vm;
      totalMaoObra += q * vo;
    });
    totalMateriaisEl.textContent = formatBRL(totalMateriais);
    totalMaoObraEl.textContent = formatBRL(totalMaoObra);
    grandTotalEl.textContent = formatBRL(totalMateriais + totalMaoObra);
  }

  function collectItems() {
    var itens = [];
    tbody.querySelectorAll("tr").forEach(function (row) {
      var desc = row.querySelector(".inp-desc").value.trim();
      var qtd = parseInt(row.querySelector(".inp-qtd").value) || 0;
      var vm = parseFloat(row.querySelector(".inp-vm").value) || 0;
      var vo = parseFloat(row.querySelector(".inp-vo").value) || 0;
      if (desc && qtd > 0) {
        itens.push({
          item: row.querySelector(".inp-item").value.trim() || "",
          descricao: desc,
          quantidade: qtd,
          valor_material: vm,
          valor_mao_obra: vo,
        });
      }
    });
    return itens;
  }

  // ============================================================
  // FORM SUBMIT
  // ============================================================
  document.getElementById("btn-add-item").addEventListener("click", addItemRow);

  document.getElementById("form-orcamento").addEventListener("submit", function (e) {
    e.preventDefault();

    var msgEl = document.getElementById("form-message");
    msgEl.style.display = "none";

    var itens = collectItems();
    if (itens.length === 0) {
      toast("Adicione pelo menos um item com descricao e quantidade.", "warning");
      return;
    }

    var payload = {
      nome: document.getElementById("nome").value.trim(),
      empresa: document.getElementById("empresa").value.trim(),
      telefone: document.getElementById("telefone").value.trim(),
      cep: document.getElementById("cep").value.trim(),
      endereco: document.getElementById("endereco").value.trim(),
      numero: document.getElementById("numero").value.trim(),
      complemento: document.getElementById("complemento").value.trim(),
      bairro: document.getElementById("bairro").value.trim(),
      cidade: document.getElementById("cidade").value.trim(),
      estado: document.getElementById("estado").value,
      validade_dias: parseInt(document.getElementById("validade_dias").value) || 15,
      observacoes: document.getElementById("observacoes").value.trim(),
      itens: itens,
    };

    if (!payload.nome || !payload.telefone || !payload.endereco || !payload.cidade) {
      toast("Preencha todos os campos obrigatorios.", "warning");
      return;
    }

    var btn = document.getElementById("btn-gerar");
    btn.disabled = true;
    btn.textContent = "Gerando PDF...";

    fetch("/api/orcamentos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        var ct = r.headers.get("Content-Type") || "";
        if (!r.ok) {
          if (ct.indexOf("application/json") !== -1) {
            return r.json().then(function (d) { throw new Error(d.error || "Erro " + r.status); });
          }
          throw new Error("Erro do servidor. Tente novamente.");
        }
        return r.json();
      })
      .then(function (data) {
        document.getElementById("modal-hash-id").textContent = data.hash_id;
        document.getElementById("link-download-pdf").href = "/pdf/" + data.hash_id;
        document.getElementById("modal-sucesso").style.display = "flex";
        toast("Orcamento " + data.hash_id + " gerado com sucesso!", "success");
        window.open("/pdf/" + data.hash_id, "_blank");
      })
      .catch(function (err) {
        toast(err.message || "Erro ao gerar orcamento.", "error");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Gerar Orcamento PDF";
      });
  });

  // Start with 1 row
  addItemRow();
})();
