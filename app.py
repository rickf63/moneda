import os
import json
from pathlib import Path

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
LOG_SCAN_LIMIT = 5000  # rango máx. de bloques por request (límite típico de RPCs públicos)
# Cuántos tramos de LOG_SCAN_LIMIT bloques se revisan hacia atrás como máximo por carga de página.
# 40 tramos x 5000 bloques = 200,000 bloques (~28 días en mainnet, ~12 s por bloque).
MAX_SCAN_CHUNKS = int(os.getenv("MAX_SCAN_CHUNKS", "40"))

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


def get_recent_transfers(decimals, limit=15):
    """Busca los transfers más recientes, revisando hacia atrás en tramos.

    Los RPC públicos limitan el rango de bloques por consulta, así que se pide de
    LOG_SCAN_LIMIT en LOG_SCAN_LIMIT bloques, del más nuevo al más viejo, hasta juntar
    `limit` transfers, llegar a DEPLOY_BLOCK o agotar MAX_SCAN_CHUNKS.
    """
    latest_block = w3.eth.block_number
    to_block = latest_block
    logs = []

    for _ in range(MAX_SCAN_CHUNKS):
        if to_block < DEPLOY_BLOCK or len(logs) >= limit:
            break
        from_block = max(DEPLOY_BLOCK, to_block - LOG_SCAN_LIMIT + 1)
        chunk = contract.events.Transfer().get_logs(
            from_block=from_block,
            to_block=to_block,
        )
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


@app.route("/", methods=["GET"])
def dashboard():
    error = None
    info = None
    transfers = []
    balance_result = None
    query_address = request.args.get("address", "").strip()

    try:
        info = get_token_info()
        transfers = get_recent_transfers(info["decimals"])
    except Exception as exc:
        error = str(exc)

    sale_info = None
    if info and tokensale_contract:
        try:
            sale_info = get_sale_info()
        except Exception:
            sale_info = None  # si falla la lectura, simplemente no se muestra la sección

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
