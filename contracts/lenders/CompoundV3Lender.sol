// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.8.18;

import {BaseStrategy} from "@tokenized-strategy/BaseStrategy.sol";

import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

import {Comet, CometRewards} from "../interfaces/Compound/V3/CompoundV3.sol";
import {ISwapRouter} from "../interfaces/Uniswap/V3/ISwapRouter.sol";

contract CompoundV3Lender is BaseStrategy {
    using SafeERC20 for ERC20;

    // To check if we shut down the vault
    bool public shutdown;

    Comet public comet;

    // Rewards Stuff
    CometRewards public constant rewardsContract =
        CometRewards(0x1B0e765F6224C21223AeA2af16c1C46E38885a40);
    //Uniswap v3 router
    ISwapRouter internal constant router =
        ISwapRouter(0xE592427A0AEce92De3Edee1F18E0157C05861564);
    //Fees for the V3 pools if the supply is incentivized
    uint24 public compToEthFee;
    uint24 public ethToAssetFee;
    address internal constant comp = 0xc00e94Cb662C3520282E6f5717214004A7f26888;
    address internal constant weth = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    uint256 public minCompToSell;

    constructor(
        address _asset,
        address _comet
    ) BaseStrategy(_asset, "yCompoundV3 Lender") {
        initializeCompoundV3Lender(_asset, _comet);
    }

    function initializeCompoundV3Lender(address _asset, address _comet) public {
        require(address(comet) == address(0), "already initialized");
        comet = Comet(_comet);
        require(comet.baseToken() == _asset, "wrong asset");

        ERC20(_asset).safeApprove(_comet, type(uint256).max);
        ERC20(comp).safeApprove(address(router), type(uint256).max);

        minCompToSell = 1e12;
    }

    function cloneCompoundV3Lender(
        address _asset,
        address _comet,
        string memory _name,
        address _management,
        address _performanceFeeRecipient,
        address _keeper
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
        compToEthFee = _compToEth;
        ethToAssetFee = _ethToAsset;
    }

    function setMinCompToSell(uint256 _minCompToSell) external onlyManagement {
        minCompToSell = _minCompToSell;
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
        require(!shutdown, "!shutdown");
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
        comet.accrueAccount(address(this));
        // Claim and sell any rewards to `asset`.
        _claimAndSellRewards();

        // deposit any loose funds
        uint256 looseAsset = ERC20(asset).balanceOf(address(this));
        if (looseAsset > 0 && !shutdown) {
            comet.supply(asset, looseAsset);
        }

        _invested =
            comet.balanceOf(address(this)) +
            ERC20(asset).balanceOf(address(this));
    }

    function _claimAndSellRewards() internal {
        rewardsContract.claim(address(comet), address(this), true);

        //check that Uni fees are not set
        if (compToEthFee == 0) return;

        uint256 _comp = ERC20(comp).balanceOf(address(this));

        if (_comp > minCompToSell) {
            if (asset == weth) {
                ISwapRouter.ExactInputSingleParams memory params = ISwapRouter
                    .ExactInputSingleParams(
                        comp, // tokenIn
                        asset, // tokenOut
                        compToEthFee, // comp-eth fee
                        address(this), // recipient
                        block.timestamp, // deadline
                        _comp, // amountIn
                        0, // amountOut
                        0 // sqrtPriceLimitX96
                    );

                router.exactInputSingle(params);
            } else {
                bytes memory path = abi.encodePacked(
                    comp, // comp-ETH
                    compToEthFee,
                    weth, // ETH-asset
                    ethToAssetFee,
                    asset
                );

                // Proceeds from Comp are not subject to minExpectedSwapPercentage
                // so they could get sandwiched if we end up in an uncle block
                router.exactInput(
                    ISwapRouter.ExactInputParams(
                        path,
                        address(this),
                        block.timestamp,
                        _comp,
                        0
                    )
                );
            }
        }
    }

    // This will shutdown the vault and withdraw any amount desired.
    // Shutdown will prevent future deposits and cannot be undone.
    function emergencyWithdraw(uint256 _amount) external onlyManagement {
        shutdown = true;
        if (_amount > 0) {
            comet.accrueAccount(address(this));
            comet.withdraw(asset, _amount);
        }
    }
}
