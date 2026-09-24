// Todo esto corre en el navegador del usuario. El backend Flask nunca ve
// ni maneja ninguna llave privada -- cada quien firma con su propia MetaMask.

const APP = window.APP_CONFIG;

let provider, signer, contract, saleContract, userAddress;

const connectBtn = document.getElementById("connect-btn");
const walletPanel = document.getElementById("wallet-panel");
const walletAddressEl = document.getElementById("wallet-address");
const walletBalanceEl = document.getElementById("wallet-balance");
const networkWarningEl = document.getElementById("network-warning");
const transferForm = document.getElementById("transfer-form");
const transferStatusEl = document.getElementById("transfer-status");

const buyForm = document.getElementById("buy-form");
const buyEthAmountEl = document.getElementById("buy-eth-amount");
const buyEstimateEl = document.getElementById("buy-estimate");
const buyStatusEl = document.getElementById("buy-status");

function shortAddress(addr) {
  return addr.slice(0, 6) + "\u2026" + addr.slice(-4);
}

// Formato fijo con coma de miles (799,999) para que no se confunda con decimales,
// sin importar el idioma del navegador.
function formatNumber(value, maxDecimals = 4) {
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: maxDecimals });
}

// Si MetaMask est\u00e1 en otra red, le pide cambiar a la red del dashboard.
// Devuelve true si ya estamos en la red correcta.
async function ensureCorrectNetwork() {
  const chainIdHex = await window.ethereum.request({ method: "eth_chainId" });
  if (chainIdHex.toLowerCase() === APP.expectedChainIdHex.toLowerCase()) {
    networkWarningEl.style.display = "none";
    return true;
  }

  try {
    await window.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: APP.expectedChainIdHex }],
    });
    // Al cambiar de red se dispara "chainChanged" y la p\u00e1gina se recarga sola.
    return false;
  } catch (err) {
    console.error(err);
    networkWarningEl.style.display = "block";
    networkWarningEl.textContent =
      "Tu MetaMask est\u00e1 en otra red. Cambia a " + APP.networkName + " para que esto funcione.";
    walletBalanceEl.textContent = "\u2014";
    return false;
  }
}

async function connectWallet() {
  if (typeof window.ethereum === "undefined") {
    transferStatusEl.textContent = "No se detectó MetaMask. Instálalo desde metamask.io";
    return;
  }

  try {
    const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
    userAddress = accounts[0];

    provider = new ethers.BrowserProvider(window.ethereum);
    signer = await provider.getSigner();
    contract = new ethers.Contract(APP.contractAddress, APP.abi, signer);
    if (APP.sale) {
      saleContract = new ethers.Contract(APP.sale.address, APP.sale.abi, signer);
    }

    connectBtn.style.display = "none";
    walletPanel.style.display = "block";

    await refreshWalletInfo();
  } catch (err) {
    console.error(err);
    transferStatusEl.textContent = "No se pudo conectar: " + (err.message || err);
  }
}

async function refreshWalletInfo() {
  walletAddressEl.textContent = shortAddress(userAddress);
  walletAddressEl.title = userAddress;

  const onRightNetwork = await ensureCorrectNetwork();
  if (!onRightNetwork) return;

  const decimals = await contract.decimals();
  const rawBalance = await contract.balanceOf(userAddress);
  const balance = ethers.formatUnits(rawBalance, decimals);
  walletBalanceEl.textContent = formatNumber(balance) + " " + APP.symbol;
}

async function handleTransfer(event) {
  event.preventDefault();

  const to = document.getElementById("transfer-to").value.trim();
  const amount = document.getElementById("transfer-amount").value.trim();

  if (!ethers.isAddress(to)) {
    transferStatusEl.textContent = "Dirección de destino inválida.";
    return;
  }
  if (!amount || Number(amount) <= 0) {
    transferStatusEl.textContent = "Escribe una cantidad válida.";
    return;
  }

  try {
    transferStatusEl.textContent = "Confirma la transacción en tu MetaMask...";
    const decimals = await contract.decimals();
    const amountWei = ethers.parseUnits(amount, decimals);

    const tx = await contract.transfer(to, amountWei);
    transferStatusEl.textContent = "Transacción enviada, esperando confirmación... hash: " + shortAddress(tx.hash);

    await tx.wait();
    transferStatusEl.textContent = "\u2705 Confirmada. Hash: " + tx.hash;

    await refreshWalletInfo();
  } catch (err) {
    console.error(err);
    const reason = err.reason || err.shortMessage || err.message || String(err);
    transferStatusEl.textContent = "Error: " + reason;
  }
}

function updateBuyEstimate() {
  if (!APP.sale || !buyEthAmountEl) return;
  const eth = Number(buyEthAmountEl.value);
  if (!eth || eth <= 0) {
    buyEstimateEl.textContent = "";
    return;
  }
  const estimatedTokens = eth * APP.sale.tokensPerEth;
  buyEstimateEl.textContent = `≈ ${formatNumber(estimatedTokens)} ${APP.symbol}`;
}

async function handleBuy(event) {
  event.preventDefault();
  if (!saleContract) {
    buyStatusEl.textContent = "La venta no está disponible ahorita.";
    return;
  }

  const ethAmount = buyEthAmountEl.value.trim();
  if (!ethAmount || Number(ethAmount) <= 0) {
    buyStatusEl.textContent = "Escribe una cantidad de ETH válida.";
    return;
  }

  try {
    buyStatusEl.textContent = "Confirma la compra en tu MetaMask...";
    const valueWei = ethers.parseEther(ethAmount);
    const tx = await saleContract.buyTokens({ value: valueWei });
    buyStatusEl.textContent = "Compra enviada, esperando confirmación... hash: " + shortAddress(tx.hash);

    await tx.wait();
    buyStatusEl.textContent = "\u2705 ¡Compra confirmada! Hash: " + tx.hash;

    await refreshWalletInfo();
  } catch (err) {
    console.error(err);
    const reason = err.reason || err.shortMessage || err.message || String(err);
    buyStatusEl.textContent = "Error: " + reason;
  }
}

connectBtn.addEventListener("click", connectWallet);
transferForm.addEventListener("submit", handleTransfer);

if (buyForm) {
  buyForm.addEventListener("submit", handleBuy);
  buyEthAmountEl.addEventListener("input", updateBuyEstimate);
}

if (typeof window.ethereum !== "undefined") {
  window.ethereum.on("accountsChanged", () => window.location.reload());
  window.ethereum.on("chainChanged", () => window.location.reload());

  // Si el usuario ya había autorizado este sitio, reconectar solo al cargar la página
  // (por ejemplo, después de cambiar de red). No abre ninguna ventana de MetaMask.
  window.ethereum
    .request({ method: "eth_accounts" })
    .then((accounts) => {
      if (accounts && accounts.length > 0) connectWallet();
    })
    .catch(() => {});
}
