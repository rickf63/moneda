# moneda — MiToken (MTK) + TokenSale + Dashboard

Proyecto Web3 full-stack de portafolio: un token **ERC-20** (`MiToken` / `MTK`), un contrato de **venta a tasa fija** (`TokenSale`) y un **panel web en Flask + web3.py** que lee los contratos en vivo y permite conectar MetaMask para enviar y comprar tokens.

Empezó en la testnet **Sepolia** y ahora está desplegado en **Ethereum mainnet**.

## Contratos en Ethereum mainnet

| Contrato | Dirección | Etherscan |
|---|---|---|
| **MiToken (MTK)** — ERC-20, 18 decimales, supply inicial 1,000,000 | `0xfE32dA5475A56091344dD43Ab074Ca033F5A8EDD` | [ver](https://etherscan.io/token/0xfE32dA5475A56091344dD43Ab074Ca033F5A8EDD) |
| **TokenSale** — 100,000 MTK por 1 ETH | `0x5B9Fc968C5A023C0093e8Da5B6C57f59e3311587` | [ver código verificado](https://etherscan.io/address/0x5B9Fc968C5A023C0093e8Da5B6C57f59e3311587#code) |

El código de `TokenSale` está verificado en Etherscan, Sourcify y Blockscout.

### Cómo funciona la venta

- La tasa es fija: **1 ETH = 100,000 MTK** (0.001 ETH = 100 MTK). Está definida como `immutable` en el constructor y no se puede cambiar.
- Para comprar basta con mandar ETH a la dirección del `TokenSale` (la función `receive()` llama a `buyTokens()`), o usar la sección "Comprar tokens" del dashboard.
- El contrato transfiere los MTK al comprador en la misma transacción. Si no hay suficientes tokens en venta, la transacción se revierte.
- El owner puede retirar el ETH recaudado (`withdraw()`) y recuperar los tokens no vendidos (`withdrawUnsoldTokens()`).

## Aviso importante

Este es un **proyecto de portafolio/aprendizaje**.

- Los contratos **no están auditados**.
- `MTK` no tiene valor garantizado ni respaldo; su "precio" es solo la tasa fija definida en el `TokenSale`.
- El owner de `MiToken` puede emitir más tokens con `mint()`, así que el supply no es fijo.
- Nada de esto es una oferta de inversión. Antes de usarlo con fondos de terceros se necesitaría una auditoría de seguridad y asesoría legal.

## Stack

- **Contratos:** Solidity 0.8.34, OpenZeppelin (ERC20, Ownable, ReentrancyGuard), desplegados desde Remix
- **Backend:** Python, Flask, web3.py (solo lectura, sin llaves privadas)
- **Frontend:** HTML/CSS, ethers.js + MetaMask (cada usuario firma desde su propio navegador)

## Dashboard

![Dashboard](docs/dashboard-screenshot.png)

Muestra:
- Nombre, símbolo, supply total y decimales del token
- Owner del contrato y su balance
- Buscador de balance por dirección
- Últimos transfers on-chain, leídos directo de los logs del contrato (sin base de datos intermedia)
- **Conectar Wallet**: cualquier usuario con MetaMask puede conectar su wallet, ver su balance y enviar tokens, firmando desde su propio navegador. El backend nunca ve ni maneja llaves privadas.
- **Comprar tokens** (opcional): si configuras `TOKENSALE_ADDRESS`, aparece una sección para comprar MTK mandando ETH desde la wallet conectada, con un estimador en vivo ETH → MTK.

### Requisitos

- Python 3.10+

### Instalación

```bash
# 1. Crear entorno virtual
python -m venv venv

# 2. Activarlo
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

### Configuración

```bash
# Windows
copy .env.example .env
# Mac/Linux
cp .env.example .env
```

En `.env` se define la red y las direcciones de los contratos (`RPC_URL`, `CONTRACT_ADDRESS`, `TOKENSALE_ADDRESS`, `CHAIN_ID`, `NETWORK_NAME`, `EXPLORER_BASE_URL`). El código no está atado a ninguna red: cambiando esos valores funciona en Sepolia o en mainnet.

### Correrlo

```bash
python app.py
```

Abre `http://127.0.0.1:5000` en tu navegador.

## Estructura

```
moneda/
├── contract/
│   ├── MiToken.sol       # Token ERC-20
│   └── TokenSale.sol     # Venta de MTK a tasa fija
├── abi/
│   ├── MiToken.json
│   └── TokenSale.json
├── app.py                # Backend Flask + web3.py
├── templates/index.html
├── static/
│   ├── style.css
│   └── wallet.js         # Conectar wallet, enviar y comprar (ethers.js)
├── docs/dashboard-screenshot.png
├── requirements.txt
├── .env.example
└── .gitignore
```

## Notas de seguridad

- El backend Flask es **solo de lectura**: no pide ni maneja llaves privadas.
- "Conectar Wallet" corre 100% en el navegador del usuario (JavaScript + MetaMask). Cada quien firma sus propias transacciones.
- El `.env` está en `.gitignore` a propósito.

## Próximos pasos posibles

- Funciones de mint/burn desde la interfaz de wallet-connect
- Gráfica de supply o de transfers en el tiempo
- Desplegar el dashboard en un servidor propio (Raspberry Pi / ThinkCentre)

## Licencia

MIT — ver [LICENSE](LICENSE).
