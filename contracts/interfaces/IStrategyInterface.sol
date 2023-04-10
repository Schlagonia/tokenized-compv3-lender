// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.8.18;

import "@tokenized-strategy/interfaces/IStrategy.sol";
import "@periphery/swappers/interfaces/IUniswapV3Swapper.sol";

interface IStrategyInterface is IStrategy, IUniswapV3Swapper {
    function cloneCompoundV3Lender(
        address _asset,
        string memory _name,
        address _management,
        address _performanceFeeRecipient,
        address _keeper,
        address _comet
    ) external returns (address newLender);

    function setUniFees(uint24 _compToEth, uint24 _ethToAsset) external;

    function setMinAmountToSell(uint256 _minAmountToSell) external;

    function emergencyWithdraw(uint256 _amount) external;
}
