// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title MiToken - Token ERC-20 de portafolio (proyecto Remix + Sepolia)
/// @notice Token de práctica desplegado en testnet Sepolia. No tiene valor real.
contract MiToken is ERC20, Ownable {
    /// @param initialSupply Cantidad inicial de tokens a mintear (en unidades enteras, sin decimales)
    constructor(uint256 initialSupply)
        ERC20("MiToken", "MTK")
        Ownable(msg.sender)
    {
        // _mint multiplica por 10^decimals automáticamente (18 decimales por default)
        _mint(msg.sender, initialSupply * 10 ** decimals());
    }

    /// @notice Permite al owner emitir más tokens (opcional, quítalo si quieres supply fijo)
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount * 10 ** decimals());
    }

    /// @notice Cualquier holder puede quemar sus propios tokens
    function burn(uint256 amount) external {
        _burn(msg.sender, amount * 10 ** decimals());
    }
}
