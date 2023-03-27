// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.8.18;

import {BaseStrategy} from "@tokenized-strategy/BaseStrategy.sol";

import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

import {IAToken} from "../interfaces/Aave/V3/IAtoken.sol";
import {IStakedAave} from "../interfaces/Aave/V3/IStakedAave.sol";
import {IPool} from "../interfaces/Aave/V3/IPool.sol";
import {IProtocolDataProvider} from "../interfaces/Aave/V3/IProtocolDataProvider.sol";
import {IRewardsController} from "../interfaces/Aave/V3/IRewardsController.sol";
import {ISwapRouter} from "../interfaces/Uniswap/V3/ISwapRouter.sol";

contract AaveV3Lender is BaseStrategy {
    using SafeERC20 for ERC20;

    // To check if we shut down the vault
    bool public shutdown;

    IProtocolDataProvider public constant protocolDataProvider =
        IProtocolDataProvider(0x7B4EB56E7CD4b454BA8ff71E4518426369a138a3);
    IPool public lendingPool;
    IRewardsController public rewardsController;
    IAToken public aToken;

    // stkAave addresses only Applicable for Mainnet, We leave then since they wont be called on any other chain
    IStakedAave internal constant stkAave =
        IStakedAave(0x4da27a545c0c5B758a6BA100e3a049001de870f5);
    address internal constant AAVE = 0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9;
    address internal constant weth = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    uint256 public minRewardToSell;

    //Uniswap v3 router
    ISwapRouter internal constant router =
        ISwapRouter(0xE592427A0AEce92De3Edee1F18E0157C05861564);

    // Fees for the Uni V3 pools
    mapping(address => mapping(address => uint24)) public uniFees;

    constructor(address _asset) BaseStrategy(_asset, "yAaveV3 Lender") {
        initializeAaveV3Lender(_asset);
    }

    function initializeAaveV3Lender(address _asset) public {
        require(address(aToken) == address(0), "already initialized");

        lendingPool = IPool(
            protocolDataProvider.ADDRESSES_PROVIDER().getPool()
        );
        aToken = IAToken(lendingPool.getReserveData(asset).aTokenAddress);
        rewardsController = aToken.getIncentivesController();

        ERC20(_asset).safeApprove(address(lendingPool), type(uint256).max);

        // Dont try and sell dust.
        minRewardToSell = 1e5;
    }

    function cloneAaveV3Lender(
        address _asset,
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
        AaveV3Lender(payable(newLender)).initializeAaveV3Lender(_asset);
    }

    //These will default to 0.
    //Will need to be manually set if asset is incentized before any harvests
    function setUniFees(
        address _token0,
        address _token1,
        uint24 _fee
    ) external onlyManagement {
        uniFees[_token0][_token1] = _fee;
        uniFees[_token1][_token0] = _fee;
    }

    function setMinRewardToSell(
        uint256 _minRewardToSell
    ) external onlyManagement {
        minRewardToSell = _minRewardToSell;
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
        lendingPool.supply(asset, _amount, address(this), 0);
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
        // We dont check available liquidity because we need the tx to
        // revert if there is not enough liquidity so we dont improperly
        // pass a loss on to the user withdrawing.
        lendingPool.withdraw(
            asset,
            Math.min(aToken.balanceOf(address(this)), _amount),
            address(this)
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
        // Claim and sell any rewards to `asset`.
        _claimAndSellRewards();

        // deposit any loose funds
        uint256 looseAsset = ERC20(asset).balanceOf(address(this));
        if (looseAsset > 0 && !shutdown) {
            lendingPool.supply(asset, looseAsset, address(this), 0);
        }

        _invested =
            aToken.balanceOf(address(this)) +
            ERC20(asset).balanceOf(address(this));
    }

    function _claimAndSellRewards() internal {
        //Need to redeem and aave from StkAave if applicable before claiming rewards and staring cool down over
        _redeemAave();

        //claim all rewards
        address[] memory assets = new address[](1);
        assets[0] = address(aToken);
        (address[] memory rewardsList, ) = rewardsController
            .claimAllRewardsToSelf(assets);

        //swap as much as possible back to want
        address token;
        for (uint256 i = 0; i < rewardsList.length; ++i) {
            token = rewardsList[i];

            if (token == address(stkAave)) {
                _harvestStkAave();
            } else if (token == asset) {
                continue;
            } else {
                _swapFrom(token, asset, ERC20(token).balanceOf(address(this)));
            }
        }
    }

    function _redeemAave() internal {
        if (!_checkCooldown()) {
            return;
        }

        uint256 stkAaveBalance = ERC20(address(stkAave)).balanceOf(
            address(this)
        );
        if (stkAaveBalance > 0) {
            stkAave.redeem(address(this), stkAaveBalance);
        }

        // sell AAVE for want
        _swapFrom(AAVE, asset, ERC20(AAVE).balanceOf(address(this)));
    }

    function _checkCooldown() internal view returns (bool) {
        if (block.chainid != 1) {
            return false;
        }

        uint256 cooldownStartTimestamp = IStakedAave(stkAave).stakersCooldowns(
            address(this)
        );
        uint256 COOLDOWN_SECONDS = IStakedAave(stkAave).COOLDOWN_SECONDS();
        uint256 UNSTAKE_WINDOW = IStakedAave(stkAave).UNSTAKE_WINDOW();
        if (block.timestamp >= cooldownStartTimestamp + COOLDOWN_SECONDS) {
            return
                block.timestamp - (cooldownStartTimestamp + COOLDOWN_SECONDS) <=
                UNSTAKE_WINDOW ||
                cooldownStartTimestamp == 0;
        } else {
            return false;
        }
    }

    function _harvestStkAave() internal {
        // request start of cooldown period
        if (ERC20(address(stkAave)).balanceOf(address(this)) > 0) {
            stkAave.cooldown();
        }
    }

    function _swapFrom(address _from, address _to, uint256 _amount) internal {
        if (_amount > minRewardToSell) {
            _checkAllowance(address(router), _from, _amount);
            if (_from == weth || _to == weth) {
                ISwapRouter.ExactInputSingleParams memory params = ISwapRouter
                    .ExactInputSingleParams(
                        _from, // tokenIn
                        _to, // tokenOut
                        uniFees[_from][_to], // comp-eth fee
                        address(this), // recipient
                        block.timestamp, // deadline
                        _amount, // amountIn
                        0, // amountOut
                        0 // sqrtPriceLimitX96
                    );

                router.exactInputSingle(params);
            } else {
                bytes memory path = abi.encodePacked(
                    _from, // comp-ETH
                    uniFees[_from][weth],
                    weth, // ETH-asset
                    uniFees[weth][_to],
                    _to
                );

                // Proceeds from Comp are not subject to minExpectedSwapPercentage
                // so they could get sandwiched if we end up in an uncle block
                router.exactInput(
                    ISwapRouter.ExactInputParams(
                        path,
                        address(this),
                        block.timestamp,
                        _amount,
                        0
                    )
                );
            }
        }
    }

    function _checkAllowance(
        address _contract,
        address _token,
        uint256 _amount
    ) internal {
        if (ERC20(_token).allowance(address(this), _contract) < _amount) {
            ERC20(_token).approve(_contract, 0);
            ERC20(_token).approve(_contract, _amount);
        }
    }

    // This will shutdown the vault and withdraw any amount desired.
    // Shutdown will prevent future deposits and cannot be undone.
    function emergencyWithdraw(uint256 _amount) external onlyManagement {
        shutdown = true;
        if (_amount > 0) {
            lendingPool.withdraw(asset, _amount, address(this));
        }
    }
}
