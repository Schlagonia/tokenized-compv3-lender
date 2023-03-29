// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.8.18;

import {BaseStrategy} from "@tokenized-strategy/BaseStrategy.sol";

import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

import {Comet, CometRewards} from "./interfaces/Compound/V3/CompoundV3.sol";

// Uniswap V3 Swapper
import {UniswapV3Swaps} from "@periphery/swaps/UniswapV3Swaps.sol";

contract CompoundV3Lender is BaseStrategy, UniswapV3Swaps {
    using SafeERC20 for ERC20;

    Comet public comet;

    // Rewards Stuff
    CometRewards public constant rewardsContract =
        CometRewards(0x1B0e765F6224C21223AeA2af16c1C46E38885a40);
    address internal constant comp = 0xc00e94Cb662C3520282E6f5717214004A7f26888;

    constructor(
        address _asset,
        string memory _name,
        address _comet
    ) BaseStrategy(_asset, _name) {
        initializeCompoundV3Lender(_asset, _comet);
    }

    function initializeCompoundV3Lender(address _asset, address _comet) public {
        require(address(comet) == address(0), "already initialized");
        comet = Comet(_comet);

        require(Comet(_comet).baseToken() == _asset, "wrong asset");

        ERC20(_asset).safeApprove(_comet, type(uint256).max);

        // Set the needed variables for the Uni Swapper
        // Base will be weth.
        base = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;

        // UniV3 mainnet router.
        router = 0xE592427A0AEce92De3Edee1F18E0157C05861564;

        // Set the min amount for the swapper to sell
        minAmountToSell = 1e12;
    }

    /*//////////////////////////////////////////////////////////////
                NEEDED TO BE OVERRIDEN BY STRATEGIST
    //////////////////////////////////////////////////////////////*/

    /**
     * @dev Should invest up to '_amount' of 'asset'.
     *
     * This function is called at the end of a {deposit} or {mint}
     * call. Meaning that unless a whitelist is implemented it will
     * be entirely permsionless and thus can be sandwhiched or otherwise
     * manipulated.
     *
     * @param _amount The amount of 'asset' that the strategy should attemppt
     * to deposit in the yield source.
     */
    function _invest(uint256 _amount) internal override {
        comet.supply(asset, _amount);
    }

    /**
     * @dev Will attempt to free the '_amount' of 'asset'.
     *
     * The amount of 'asset' that is already loose has already
     * been accounted for.
     *
     * Should do any needed parameter checks, '_amount' may be more
     * than is actually available.
     *
     * This function is called {withdraw} and {redeem} calls.
     * Meaning that unless a whitelist is implemented it will be
     * entirely permsionless and thus can be sandwhiched or otherwise
     * manipulated.
     *
     * Should not rely on asset.balanceOf(address(this)) calls other than
     * for diff accounting puroposes.
     *
     * @param _amount, The amount of 'asset' to be freed.
     */
    function _freeFunds(uint256 _amount) internal override {
        // Need the balance updated
        comet.accrueAccount(address(this));
        // We dont check available liquidity because we need the tx to
        // revert if there is not enough liquidity so we dont improperly
        // pass a loss on to the user withdrawing.
        comet.withdraw(
            asset,
            Math.min(comet.balanceOf(address(this)), _amount)
        );
    }

    /**
     * @dev Internal non-view function to harvest all rewards, reinvest
     * and return the accurate amount of funds currently held by the Strategy.
     *
     * This should do any needed harvesting, rewards selling, accrual,
     * reinvesting etc. to get the most accurate view of current assets.
     *
     * All applicable assets including loose assets should be accounted
     * for in this function.
     *
     * Care should be taken when relying on oracles or swap values rather
     * than actual amounts as all Strategy profit/loss accounting will
     * be done based on this returned value.
     *
     * @return _invested A trusted and accurate account for the total
     * amount of 'asset' the strategy currently holds.
     */
    function _totalInvested() internal override returns (uint256 _invested) {
        // Only sell and reinvest if we arent shutdown
        if (!BaseLibrary.isShutdown()) {
            // Claim and sell any rewards to `asset`. Claims will accure account
            rewardsContract.claim(address(comet), address(this), true);

            uint256 _comp = ERC20(comp).balanceOf(address(this));

            // The uni swapper will do min checks on _comp.
            _swapFrom(comp, asset, _comp, 0);

            // deposit any loose funds
            uint256 looseAsset = ERC20(asset).balanceOf(address(this));
            if (looseAsset > 0) {
                comet.supply(asset, looseAsset);
            }
        }

        _invested =
            comet.balanceOf(address(this)) +
            ERC20(asset).balanceOf(address(this));
    }

    function cloneCompoundV3Lender(
        address _asset,
        string memory _name,
        address _management,
        address _performanceFeeRecipient,
        address _keeper,
        address _comet
    ) external returns (address newLender) {
        // Use the cloning logic held withen the Base library.
        newLender = BaseLibrary.clone(
            _asset,
            _name,
            _management,
            _performanceFeeRecipient,
            _keeper
        );
        // Neeed to cast address to payable since there is a fallback function.
        CompoundV3Lender(payable(newLender)).initializeCompoundV3Lender(
            _asset,
            _comet
        );
    }

    //These will default to 0.
    //Will need to be manually set if asset is incentized before any harvests
    function setUniFees(
        uint24 _compToEth,
        uint24 _ethToAsset
    ) external onlyManagement {
        _setUniFees(comp, base, _compToEth);
        _setUniFees(base, asset, _ethToAsset);
    }

    function setMinAmountToSell(
        uint256 _minAmountToSell
    ) external onlyManagement {
        minAmountToSell = _minAmountToSell;
    }

    // This should can be used in conjunction with shutting down the
    // strategy in an emgency to liquidate the strategy.
    // A report will need to be called post an emergency withdraw to record
    // the updates in totalDebt and totalIdle
    function emergencyWithdraw(uint256 _amount) external onlyManagement {
        comet.accrueAccount(address(this));
        comet.withdraw(asset, _amount);
    }
}
