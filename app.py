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
LOG_SCAN_LIMIT = 5000  # rango máx. de bloques por request (límite típico de RPCs públicos)

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
    """Escanea los logs del evento Transfer desde el bloque de despliegue."""
    latest_block = w3.eth.block_number
    start_block = max(DEPLOY_BLOCK, latest_block - LOG_SCAN_LIMIT)

    logs = contract.events.Transfer().get_logs(
        from_block=start_block,
        to_block=latest_block,
    )

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
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
