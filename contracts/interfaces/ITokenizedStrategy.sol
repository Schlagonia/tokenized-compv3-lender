// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.8.18;

import "@tokenized-strategy/interfaces/IStrategy.sol";

interface ITokenizedStrategy is IStrategy {
    function cloneCompoundV3Lender(
        address _asset,
        address _comet,
        string memory _name,
        address _management,
        address _performanceFeeRecipient,
        address _keeper
    ) external returns (address newLender);

    function setUniFees(uint24 _compToEth, uint24 _ethToAsset) external;

    function uniFees(address, address) external view returns (uint24);

    function minAmountToSell() external view returns (uint256);

    function setMinAmountToSell(uint256 _minAmountToSell) external;

    function emergencyWithdraw(uint256 _amount) external;
}
