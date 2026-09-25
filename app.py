import os
import json
import time
import threading
from pathlib import Path

import requests
from flask import Flask, render_template, request
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
DEPLOY_BLOCK = int(os.getenv("DEPLOY_BLOCK", "0"))
CHAIN_ID = int(os.getenv("CHAIN_ID", "11155111"))  # 11155111 = Sepolia, 1 = mainnet
NETWORK_NAME = os.getenv("NETWORK_NAME", "Sepolia")
EXPLORER_BASE_URL = os.getenv("EXPLORER_BASE_URL", "https://sepolia.etherscan.io").rstrip("/")
TOKENSALE_ADDRESS = os.getenv("TOKENSALE_ADDRESS", "").strip()  # opcional
# Opcional pero recomendado: API key gratis de Etherscan (etherscan.io/myapikey).
# Con ella los transfers se leen en UNA consulta, sin depender de los límites de eth_getLogs del RPC.
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()
ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"
# Rango máx. de bloques por consulta de logs. Cada RPC tiene su propio límite; si una
# consulta falla, el rango se parte a la mitad automáticamente (ver get_recent_transfers).
LOG_SCAN_LIMIT = int(os.getenv("LOG_SCAN_LIMIT", "5000"))
MIN_LOG_SCAN = 100
# Máximo de consultas de logs por carga de página (evita saturar al RPC).
MAX_LOG_REQUESTS = int(os.getenv("MAX_LOG_REQUESTS", "40"))

BASE_DIR = Path(__file__).resolve().parent

if not CONTRACT_ADDRESS:
    raise RuntimeError(
        "Falta CONTRACT_ADDRESS en tu archivo .env. "
        "Copia .env.example a .env (cp .env.example .env / copy .env.example .env) "
        "y confirma que tenga la dirección de tu contrato."
    )

app = Flask(__name__)

w3 = Web3(Web3.HTTPProvider(RPC_URL))

with open(BASE_DIR / "abi" / "MiToken.json", encoding="utf-8") as f:
    CONTRACT_ABI = json.load(f)

contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=CONTRACT_ABI,
)

TOKENSALE_ABI = None
tokensale_contract = None
if TOKENSALE_ADDRESS:
    with open(BASE_DIR / "abi" / "TokenSale.json", encoding="utf-8") as f:
        TOKENSALE_ABI = json.load(f)
    tokensale_contract = w3.eth.contract(
        address=Web3.to_checksum_address(TOKENSALE_ADDRESS),
        abi=TOKENSALE_ABI,
    )


def describe_error(exc):
    """Texto corto del error para el log del servidor (incluye la respuesta del RPC si la hay)."""
    msg = str(exc)
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            msg += " | respuesta: " + response.text[:300]
        except Exception:
            pass
    return msg


def get_sale_info():
    """Lee la tasa de cambio y cuántos tokens quedan disponibles en la venta."""
    if not tokensale_contract:
        return None
    tokens_per_eth = tokensale_contract.functions.tokensPerEth().call()
    remaining_raw = contract.functions.balanceOf(TOKENSALE_ADDRESS).call()
    decimals = contract.functions.decimals().call()
    return {
        "address": TOKENSALE_ADDRESS,
        "tokens_per_eth": tokens_per_eth,
        "remaining": remaining_raw / (10 ** decimals),
    }


def get_token_info():
    """Lee los datos base del token directo de la blockchain."""
    decimals = contract.functions.decimals().call()
    total_supply_raw = contract.functions.totalSupply().call()
    owner_address = contract.functions.owner().call()
    owner_balance_raw = contract.functions.balanceOf(owner_address).call()

    return {
        "name": contract.functions.name().call(),
        "symbol": contract.functions.symbol().call(),
        "decimals": decimals,
        "total_supply": total_supply_raw / (10 ** decimals),
        "owner": owner_address,
        "owner_balance": owner_balance_raw / (10 ** decimals),
        "address": CONTRACT_ADDRESS,
        "latest_block": w3.eth.block_number,
    }


def get_transfers_etherscan(decimals, limit=15):
    """Últimos transfers del token vía la API de Etherscan (una sola consulta)."""
    resp = requests.get(
        ETHERSCAN_API_URL,
        params={
            "chainid": CHAIN_ID,
            "module": "account",
            "action": "tokentx",
            "contractaddress": CONTRACT_ADDRESS,
            "page": 1,
            "offset": limit,
            "sort": "desc",
            "apikey": ETHERSCAN_API_KEY,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "1":
        if "no transactions found" in str(data.get("message", "")).lower():
            return []
        raise RuntimeError(f"Etherscan: {data.get('message')} - {str(data.get('result'))[:200]}")

    return [
        {
            "from": Web3.to_checksum_address(tx["from"]),
            "to": Web3.to_checksum_address(tx["to"]),
            "value": int(tx["value"]) / (10 ** decimals),
            "block": int(tx["blockNumber"]),
            "tx_hash": tx["hash"],
        }
        for tx in data["result"][:limit]
    ]


def get_recent_transfers(decimals, limit=15):
    """Últimos transfers: Etherscan si hay API key; si no (o si falla), logs del RPC."""
    if ETHERSCAN_API_KEY:
        try:
            return get_transfers_etherscan(decimals, limit)
        except Exception as exc:
            app.logger.warning("Etherscan falló, usando logs del RPC: %s", describe_error(exc))
    return get_transfers_from_logs(decimals, limit)


def get_transfers_from_logs(decimals, limit=15):
    """Busca los transfers más recientes, revisando hacia atrás en tramos.

    Los RPC limitan el rango de bloques por consulta, así que se pide por tramos del
    más nuevo al más viejo, hasta juntar `limit` transfers, llegar a DEPLOY_BLOCK o
    agotar MAX_LOG_REQUESTS. Si el RPC rechaza un tramo, se reintenta con la mitad.
    """
    latest_block = w3.eth.block_number
    to_block = latest_block
    step = LOG_SCAN_LIMIT
    logs = []

    for _ in range(MAX_LOG_REQUESTS):
        if to_block < DEPLOY_BLOCK or len(logs) >= limit:
            break
        from_block = max(DEPLOY_BLOCK, to_block - step + 1)
        try:
            chunk = contract.events.Transfer().get_logs(
                from_block=from_block,
                to_block=to_block,
            )
        except Exception as exc:
            if step <= MIN_LOG_SCAN:
                raise
            step = max(MIN_LOG_SCAN, step // 2)
            app.logger.warning("RPC rechazó rango de logs; reintentando con %s bloques (%s)", step, describe_error(exc))
            continue
        logs = list(chunk) + logs  # mantener orden cronológico
        to_block = from_block - 1

    transfers = []
    for log in reversed(logs[-limit:]):
        transfers.append({
            "from": log["args"]["from"],
            "to": log["args"]["to"],
            "value": log["args"]["value"] / (10 ** decimals),
            "block": log["blockNumber"],
            "tx_hash": w3.to_hex(log["transactionHash"]),
        })
    return transfers


def get_balance(address, decimals):
    """Consulta el balance de una dirección arbitraria."""
    checksum = Web3.to_checksum_address(address)
    raw_balance = contract.functions.balanceOf(checksum).call()
    return {
        "address": checksum,
        "balance": raw_balance / (10 ** decimals),
    }


# Caché corto de lo que se lee de la blockchain: si varias personas abren la página
# al mismo tiempo, no se repiten las mismas consultas al RPC público.
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
_cache = {"at": 0.0, "data": None}
_cache_lock = threading.Lock()


def get_chain_data():
    """Datos del token, transfers y venta, con caché de CACHE_TTL_SECONDS."""
    with _cache_lock:
        if _cache["data"] and time.time() - _cache["at"] < CACHE_TTL_SECONDS:
            return _cache["data"]

        info = get_token_info()
        try:
            transfers = get_recent_transfers(info["decimals"])
        except Exception as exc:
            # Sin transfers la página sigue funcionando (balance, wallet y compra)
            app.logger.warning("No se pudieron leer los transfers: %s", describe_error(exc))
            transfers = None
        sale_info = None
        if tokensale_contract:
            try:
                sale_info = get_sale_info()
            except Exception as exc:
                app.logger.warning("No se pudo leer el TokenSale: %s", describe_error(exc))

        _cache["data"] = (info, transfers, sale_info)
        _cache["at"] = time.time()
        return _cache["data"]


@app.after_request
def add_security_headers(response):
    # Evita que otra página meta el dashboard en un iframe para engañar clics (clickjacking)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.route("/", methods=["GET"])
def dashboard():
    error = None
    info = None
    transfers = []
    sale_info = None
    balance_result = None
    query_address = request.args.get("address", "").strip()

    try:
        info, transfers, sale_info = get_chain_data()
    except Exception as exc:
        # El detalle va al log del servidor; al visitante no se le muestran datos internos
        app.logger.error("Error leyendo la blockchain: %s", describe_error(exc))
        error = "No se pudo conectar con la blockchain en este momento. Intenta de nuevo en un minuto."

    if info and query_address:
        try:
            balance_result = get_balance(query_address, info["decimals"])
        except Exception:
            balance_result = {"error": "Esa dirección no es válida."}

    return render_template(
        "index.html",
        info=info,
        transfers=transfers,
        balance_result=balance_result,
        query_address=query_address,
        error=error,
        abi_json=CONTRACT_ABI,
        chain_id_hex=hex(CHAIN_ID),
        network_name=NETWORK_NAME,
        explorer_base_url=EXPLORER_BASE_URL,
        sale_info=sale_info,
        tokensale_abi_json=TOKENSALE_ABI,
    )


if __name__ == "__main__":
    app.run(debug=False, port=5000)
