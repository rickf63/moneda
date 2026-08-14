# MiToken Dashboard

Panel web en **Flask + web3.py** que lee en vivo el contrato ERC-20 `MiToken` (`MTK`) desplegado en la testnet de **Sepolia**.

Muestra:
- Nombre, símbolo, supply total y decimales del token
- Owner del contrato y su balance
- Buscador de balance por dirección
- Últimos transfers on-chain, leídos directo de los logs del contrato (sin base de datos intermedia)

## Requisitos

- Python 3.10+
- El contrato `MiToken.sol` ya desplegado (se desplegó desde Remix a Sepolia)

## Instalación

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

## Configuración

```bash
# Windows
copy .env.example .env
# Mac/Linux
cp .env.example .env
```

El `.env` ya trae precargada la dirección del contrato y un RPC público de Sepolia que no requiere registro. Si más adelante quieres más velocidad o confiabilidad, puedes reemplazar `RPC_URL` por un endpoint propio de Alchemy o Infura (gratis, solo pide cuenta).

## Correrlo

```bash
python app.py
```

Abre `http://127.0.0.1:5000` en tu navegador.

## Estructura

```
erc20_dashboard/
├── app.py              # Backend Flask + web3.py
├── abi/MiToken.json    # ABI del contrato
├── templates/index.html
├── static/style.css
├── requirements.txt
├── .env.example
└── .gitignore
```

## Notas de seguridad

- Este dashboard es **solo de lectura**: no pide ni maneja llaves privadas.
- El `.env` está en `.gitignore` a propósito. Aun así, como todo lo que contiene son datos públicos de un contrato en testnet (no hay dinero real ni claves), no pasa nada grave si se sube por accidente — pero es buena práctica de todos modos.

## Próximos pasos posibles

- Botón para transferir/mintear tokens desde el dashboard (requeriría firmar con una clave privada — usa siempre una wallet dedicada de pruebas, nunca la que tenga fondos reales)
- Gráfica de supply o de transfers en el tiempo
- Desplegar el dashboard en un servidor propio (tu Raspberry Pi / ThinkCentre)
