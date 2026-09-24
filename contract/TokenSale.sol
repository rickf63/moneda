// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title TokenSale - Vende MiToken (MTK) a cambio de ETH a una tasa fija
/// @notice Contrato de práctica/portafolio para testnet. NO está auditado.
///         No se debe usar en mainnet con fondos de terceros sin revisión profesional
///         (auditoría de seguridad + asesoría legal), ver README para más contexto.
contract TokenSale is Ownable, ReentrancyGuard {
    IERC20Metadata public immutable token;
    uint256 public immutable tokensPerEth; // cuántos MTK (unidades enteras) por 1 ETH
    uint256 public weiRaised;

    event TokensPurchased(address indexed buyer, uint256 weiPaid, uint256 tokensSent);
    event Withdrawn(address indexed to, uint256 amount);

    constructor(address tokenAddress, uint256 _tokensPerEth) Ownable(msg.sender) {
        require(tokenAddress != address(0), "token invalido");
        require(_tokensPerEth > 0, "tasa invalida");
        token = IERC20Metadata(tokenAddress);
        tokensPerEth = _tokensPerEth;
    }

    /// @notice Compra tokens mandando ETH a esta función.
    function buyTokens() public payable nonReentrant {
        require(msg.value > 0, "manda algo de ETH");

        uint256 tokenAmount = (msg.value * tokensPerEth * (10 ** token.decimals())) / 1 ether;
        require(tokenAmount > 0, "monto muy pequeno para comprar 1 unidad");
        require(token.balanceOf(address(this)) >= tokenAmount, "no hay suficiente supply en venta");

        weiRaised += msg.value;

        bool sent = token.transfer(msg.sender, tokenAmount);
        require(sent, "fallo la transferencia de tokens");

        emit TokensPurchased(msg.sender, msg.value, tokenAmount);
    }

    /// @notice Si alguien manda ETH directo a la dirección del contrato, cuenta como compra.
    receive() external payable {
        buyTokens();
    }

    /// @notice El owner retira el ETH recaudado hasta ahora.
    function withdraw() external onlyOwner nonReentrant {
        uint256 balance = address(this).balance;
        require(balance > 0, "no hay fondos que retirar");
        (bool success, ) = payable(owner()).call{value: balance}("");
        require(success, "fallo el retiro");
        emit Withdrawn(owner(), balance);
    }

    /// @notice El owner puede recuperar tokens que no se vendieron (ej. para cerrar la venta).
    function withdrawUnsoldTokens() external onlyOwner {
        uint256 remaining = token.balanceOf(address(this));
        require(remaining > 0, "no quedan tokens sin vender");
        bool sent = token.transfer(owner(), remaining);
        require(sent, "fallo la transferencia");
    }
}
